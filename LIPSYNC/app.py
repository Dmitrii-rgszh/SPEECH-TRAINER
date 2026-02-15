from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Optional

from flask import Flask, jsonify, request, send_file

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


def _log_error(message: str) -> None:
    try:
        err_path = _resolve_path("LIPSYNC/error.log", ROOT_DIR)
        with open(err_path, "a", encoding="utf-8") as f:
            f.write("\n" + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write(message + "\n")
    except Exception:
        pass


@app.errorhandler(Exception)
def handle_error(err: Exception):
    _log_error(traceback.format_exc())
    return jsonify({"error": str(err)}), 500


def _load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _cfg_get(cfg: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = cfg
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def _resolve_path(path_value: str, base: Path) -> Path:
    raw = Path(path_value)
    if raw.is_absolute():
        return raw
    return (base / raw).resolve()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _pick_latest_mp4(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    candidates = list(path.rglob("*.mp4"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _reencode_h264(input_path: Path, ffmpeg_path: str, tmp_dir: Path) -> Path:
    """Re-encode video to H.264 for browser compatibility."""
    output_path = tmp_dir / f"h264_{input_path.name}"
    cmd = [
        ffmpeg_path, "-y", "-i", str(input_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        if output_path.exists():
            return output_path
    except Exception:
        pass
    return input_path


def _find_python_in_venv(venv_dir: Path) -> Optional[Path]:
    if os.name == "nt":
        exe = venv_dir / "Scripts" / "python.exe"
    else:
        exe = venv_dir / "bin" / "python"
    return exe if exe.exists() else None


def _resolve_repo(cfg: dict[str, Any], key: str, default: str) -> Path:
    value = _cfg_get(cfg, key)
    if value:
        return _resolve_path(str(value), ROOT_DIR)
    return _resolve_path(default, ROOT_DIR)


def _ffmpeg_path(cfg: dict[str, Any]) -> Optional[str]:
    value = _cfg_get(cfg, "lip_sync", "ffmpeg_path")
    if value:
        return str(_resolve_path(str(value), ROOT_DIR))
    return shutil.which("ffmpeg")


def _pipeline_settings() -> dict[str, Any]:
    cfg = _load_config()
    lip_cfg = cfg.get("lip_sync_legacy") if isinstance(cfg.get("lip_sync_legacy"), dict) else None
    if not lip_cfg:
        lip_cfg = cfg.get("lip_sync") if isinstance(cfg.get("lip_sync"), dict) else {}
    work_dir = _resolve_path(
        str(_cfg_get(lip_cfg, "work_dir", default="CLEAN_AVATARS")),
        ROOT_DIR,
    )
    musetalk_tmp = _cfg_get(lip_cfg, "musetalk_tmp_dir", default="E:/musetalk_tmp")
    return {
        "cfg": cfg,
        "lip_cfg": lip_cfg,
        "work_dir": work_dir,
        "sadtalker_dir": _resolve_repo(lip_cfg, "sadtalker_repo", "CLEAN_AVATARS/PIPELINE/SadTalker"),
        "musetalk_dir": _resolve_repo(lip_cfg, "musetalk_repo", "CLEAN_AVATARS/PIPELINE/MuseTalk"),
        "codeformer_dir": _resolve_repo(lip_cfg, "codeformer_repo", "CLEAN_AVATARS/PIPELINE/CodeFormer"),
        "ffmpeg": _ffmpeg_path(cfg),
        "use_cuda": bool(_cfg_get(lip_cfg, "use_cuda", default=True)),
        "pipeline": str(_cfg_get(lip_cfg, "pipeline", default="full")).lower(),
        "face_restorer": str(_cfg_get(lip_cfg, "face_restorer", default="codeformer")).lower(),
        "enhancer": str(_cfg_get(lip_cfg, "enhancer", default="gfpgan")).lower(),
        "python_exe": str(_cfg_get(lip_cfg, "python_exe", default="")),
        "musetalk_tmp_dir": _resolve_path(str(musetalk_tmp), ROOT_DIR),
        "error_log": str(_resolve_path("LIPSYNC/error.log", ROOT_DIR)),
    }


def _get_avatar_path(cfg: dict[str, Any]) -> Optional[Path]:
    avatar = _cfg_get(cfg, "ui", "avatar_path")
    if not avatar:
        return None
    return _resolve_path(str(avatar), ROOT_DIR)


def _run_command(cmd: list[str], cwd: Path, env: dict[str, str]) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout[-4000:])
    return proc.stdout


def _ensure_repo(path: Path, name: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{name} repo not found at {path}. Clone it first (see LIPSYNC/README.md)."
        )


def _prepare_env(use_cuda: bool) -> dict[str, str]:
    env = os.environ.copy()
    if not use_cuda:
        env["CUDA_VISIBLE_DEVICES"] = ""
    env.setdefault("HF_HUB_DISABLE_SAFE_WEIGHTS", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _run_sadtalker(
    cfg: dict[str, Any],
    sadtalker_dir: Path,
    audio_path: Path,
    avatar_path: Path,
    output_dir: Path,
    python_exe: str,
    use_cuda: bool,
) -> Path:
    _ensure_repo(sadtalker_dir, "SadTalker")
    _ensure_dir(output_dir)
    enhancer = str(_cfg_get(cfg, "lip_sync", "enhancer", default="gfpgan")).lower()
    enhancer_arg = enhancer if enhancer in {"gfpgan", "gpen", "none"} else "gfpgan"

    def run_with_enhancer(enhancer_value: str) -> Optional[str]:
        cmd = [
            python_exe,
            "inference.py",
            "--driven_audio",
            str(audio_path),
            "--source_image",
            str(avatar_path),
            "--result_dir",
            str(output_dir),
            "--still",
            "--preprocess",
            "full",
        ]
        if enhancer_value != "none":
            cmd += ["--enhancer", enhancer_value]

        try:
            return _run_command(cmd, sadtalker_dir, _prepare_env(use_cuda))
        except RuntimeError as exc:
            return str(exc)

    output = run_with_enhancer(enhancer_arg)
    result = _pick_latest_mp4(output_dir)
    if result:
        return result

    if enhancer_arg != "none":
        output = run_with_enhancer("none")
        result = _pick_latest_mp4(output_dir)
        if result:
            return result

    raise RuntimeError(
        "SadTalker did not produce an output video.\n"
        + (output.strip()[-2000:] if output else "")
    )


def _run_musetalk(
    cfg: dict[str, Any],
    musetalk_dir: Path,
    video_path: Path,
    audio_path: Path,
    output_dir: Path,
    python_exe: str,
    ffmpeg_path: str,
    use_cuda: bool,
    tmp_dir_base: Path,
) -> Path:
    _ensure_repo(musetalk_dir, "MuseTalk")
    _ensure_dir(output_dir)

    inference_cfg = musetalk_dir / "configs" / "inference" / "test.yaml"
    if not inference_cfg.exists():
        raise FileNotFoundError("MuseTalk inference config not found.")

    tmp_cfg = output_dir / "musetalk_inference.yaml"
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required for MuseTalk.") from exc

    base_cfg = yaml.safe_load(inference_cfg.read_text(encoding="utf-8")) or {}
    bbox_shift = _cfg_get(cfg, "lip_sync", "musetalk_bbox_shift")

    _ensure_dir(tmp_dir_base)
    with tempfile.TemporaryDirectory(dir=tmp_dir_base) as temp_input_dir:
        temp_dir_path = Path(temp_input_dir)
        safe_video = temp_dir_path / "input.mp4"
        safe_audio = temp_dir_path / "input.wav"
        temp_output_dir = temp_dir_path / "out"
        _ensure_dir(temp_output_dir)
        shutil.copy2(video_path, safe_video)
        shutil.copy2(audio_path, safe_audio)

        task_cfg = {
            "video_path": str(safe_video),
            "audio_path": str(safe_audio),
        }
        if bbox_shift is not None:
            task_cfg["bbox_shift"] = bbox_shift
        data = {"task_0": task_cfg}
        if isinstance(base_cfg, dict):
            for key in ("preparation", "fps", "use_cpu"):
                if key in base_cfg:
                    data[key] = base_cfg[key]
        tmp_cfg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

        version = str(_cfg_get(cfg, "lip_sync", "musetalk_version", default="v15"))
        unet_model = _resolve_path(
            str(
                _cfg_get(
                    cfg,
                    "lip_sync",
                    "musetalk_unet",
                    default="CLEAN_AVATARS/PIPELINE/MuseTalk/models/musetalkV15/unet.pth",
                )
            ),
            ROOT_DIR,
        )
        unet_cfg = _resolve_path(
            str(
                _cfg_get(
                    cfg,
                    "lip_sync",
                    "musetalk_unet_cfg",
                    default="CLEAN_AVATARS/PIPELINE/MuseTalk/models/musetalkV15/musetalk.json",
                )
            ),
            ROOT_DIR,
        )

        cmd = [
            python_exe,
            "-m",
            "scripts.inference",
            "--inference_config",
            str(tmp_cfg),
            "--result_dir",
            str(temp_output_dir),
            "--unet_model_path",
            str(unet_model),
            "--unet_config",
            str(unet_cfg),
            "--version",
            version,
            "--ffmpeg_path",
            str(ffmpeg_path),
        ]

        debug_header = (
            f"MuseTalk temp input: {safe_video} | {safe_audio}\n"
            f"MuseTalk temp output: {temp_output_dir}\n"
        )
        try:
            output = _run_command(cmd, musetalk_dir, _prepare_env(use_cuda))
        except RuntimeError as exc:
            output = str(exc)

        result = _pick_latest_mp4(temp_output_dir)
        if not result:
            tail = (output or "").strip()[-2000:]
            raise RuntimeError(
                "MuseTalk did not produce an output video.\n"
                + debug_header
                + "Output:\n"
                + (tail or "<no output>")
            )
        _ensure_dir(output_dir)
        final_path = output_dir / result.name
        shutil.copy2(result, final_path)
        return final_path


def _run_codeformer(
    codeformer_dir: Path,
    video_path: Path,
    output_dir: Path,
    python_exe: str,
    use_cuda: bool,
    tmp_dir_base: Path,
) -> Path:
    _ensure_repo(codeformer_dir, "CodeFormer")
    _ensure_dir(output_dir)

    _ensure_dir(tmp_dir_base)
    with tempfile.TemporaryDirectory(dir=tmp_dir_base) as temp_dir:
        temp_dir_path = Path(temp_dir)
        safe_video = temp_dir_path / "input.mp4"
        shutil.copy2(video_path, safe_video)

        cmd = [
            python_exe,
            "inference_codeformer.py",
            "--bg_upsampler",
            "realesrgan",
            "--face_upsample",
            "-w",
            "0.7",
            "--input_path",
            str(safe_video),
        ]

        _run_command(cmd, codeformer_dir, _prepare_env(use_cuda))
        default_out = codeformer_dir / "results"
        result = _pick_latest_mp4(output_dir) or _pick_latest_mp4(default_out)
        if not result:
            raise RuntimeError("CodeFormer did not produce an output video.")
        return result


@app.get("/health")
def health():
    settings = _pipeline_settings()
    return jsonify(
        {
            "status": "ok",
            "pipeline": settings["pipeline"],
            "use_cuda": settings["use_cuda"],
            "ffmpeg": bool(settings["ffmpeg"]),
        }
    )


@app.post("/generate")
def generate():
    settings = _pipeline_settings()
    cfg = settings["cfg"]
    ffmpeg_path = settings["ffmpeg"]
    if not ffmpeg_path:
        return jsonify({"error": "ffmpeg not found in PATH or config"}), 500

    avatar_path = _get_avatar_path(cfg)
    if not avatar_path or not avatar_path.exists():
        return jsonify({"error": "avatar_path not found"}), 400

    if "audio" not in request.files:
        return jsonify({"error": "audio file is required"}), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        return jsonify({"error": "empty filename"}), 400

    work_dir = settings["work_dir"]
    _ensure_dir(work_dir)

    python_exe = settings["python_exe"]
    if python_exe:
        python_path = _resolve_path(python_exe, ROOT_DIR)
        python_exe = str(python_path)
    else:
        python_exe = sys.executable

    try:
        with tempfile.TemporaryDirectory(dir=work_dir) as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            audio_path = tmp_dir_path / "audio.wav"
            audio_file.save(audio_path)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            result_root = work_dir / "RESULTS" / timestamp
            sadtalker_out = result_root / "sadtalker"
            musetalk_out = result_root / "musetalk"
            restore_out = result_root / "restore"

            current_video = _run_sadtalker(
                cfg,
                settings["sadtalker_dir"],
                audio_path,
                avatar_path,
                sadtalker_out,
                python_exe,
                settings["use_cuda"],
            )

            if settings["pipeline"] in {"full", "musetalk"}:
                current_video = _run_musetalk(
                    cfg,
                    settings["musetalk_dir"],
                    current_video,
                    audio_path,
                    musetalk_out,
                    python_exe,
                    ffmpeg_path,
                    settings["use_cuda"],
                    settings["musetalk_tmp_dir"],
                )

            if settings["face_restorer"] == "codeformer":
                current_video = _run_codeformer(
                    settings["codeformer_dir"],
                    current_video,
                    restore_out,
                    python_exe,
                    settings["use_cuda"],
                    settings["musetalk_tmp_dir"],
                )

            # Re-encode to H.264 for browser compatibility
            current_video = _reencode_h264(
                current_video,
                ffmpeg_path,
                Path(settings["musetalk_tmp_dir"]),
            )

            return send_file(
                current_video,
                mimetype="video/mp4",
                as_attachment=False,
                max_age=0,
            )
    except Exception as exc:
        err_path = settings.get("error_log")
        if err_path:
            try:
                with open(err_path, "a", encoding="utf-8") as f:
                    f.write("\n" + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
                    f.write(traceback.format_exc())
            except Exception:
                pass
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    cfg = _load_config()
    lip_cfg = cfg.get("lip_sync_legacy") if isinstance(cfg.get("lip_sync_legacy"), dict) else None
    if not lip_cfg:
        lip_cfg = cfg.get("lip_sync") if isinstance(cfg.get("lip_sync"), dict) else {}
    host = _cfg_get(lip_cfg, "host", default="127.0.0.1")
    port = int(_cfg_get(lip_cfg, "port", default=7002))
    app.run(host=host, port=port, debug=False, threaded=True)
