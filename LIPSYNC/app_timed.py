"""
LIPSYNC app.py with DETAILED TIMINGS
====================================
Добавлены тайминги по каждому этапу для анализа bottleneck.
"""

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

# ============== TIMING STORAGE ==============
LAST_TIMINGS = {}


def _log_timing(name: str, elapsed: float):
    """Store and print timing."""
    LAST_TIMINGS[name] = elapsed
    print(f"[TIMING] {name}: {elapsed:.2f}s")


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
    value = _cfg_get(cfg, "lip_sync", key)
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
    work_dir = _resolve_path(
        str(_cfg_get(cfg, "lip_sync", "work_dir", default="CLEAN_AVATARS")),
        ROOT_DIR,
    )
    musetalk_tmp = _cfg_get(cfg, "lip_sync", "musetalk_tmp_dir", default="E:/musetalk_tmp")
    return {
        "cfg": cfg,
        "work_dir": work_dir,
        "sadtalker_dir": _resolve_repo(cfg, "sadtalker_repo", "CLEAN_AVATARS/PIPELINE/SadTalker"),
        "musetalk_dir": _resolve_repo(cfg, "musetalk_repo", "CLEAN_AVATARS/PIPELINE/MuseTalk"),
        "codeformer_dir": _resolve_repo(cfg, "codeformer_repo", "CLEAN_AVATARS/PIPELINE/CodeFormer"),
        "ffmpeg": _ffmpeg_path(cfg),
        "use_cuda": bool(_cfg_get(cfg, "lip_sync", "use_cuda", default=True)),
        "pipeline": str(_cfg_get(cfg, "lip_sync", "pipeline", default="full")).lower(),
        "face_restorer": str(_cfg_get(cfg, "lip_sync", "face_restorer", default="codeformer")).lower(),
        "enhancer": str(_cfg_get(cfg, "lip_sync", "enhancer", default="gfpgan")).lower(),
        "python_exe": str(_cfg_get(cfg, "lip_sync", "python_exe", default="")),
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
            "inference_timed.py",  # USE TIMED VERSION
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


@app.get("/timings")
def get_timings():
    """Return last request timings."""
    return jsonify(LAST_TIMINGS)


@app.post("/generate")
def generate():
    global LAST_TIMINGS
    LAST_TIMINGS = {}
    
    t_total_start = time.time()
    
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
            
            # TIMING: Save audio
            t0 = time.time()
            audio_path = tmp_dir_path / "audio.wav"
            audio_file.save(audio_path)
            _log_timing("save_audio", time.time() - t0)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            result_root = work_dir / "RESULTS" / timestamp
            sadtalker_out = result_root / "sadtalker"

            # TIMING: SadTalker (includes model load + preprocess + inference + render)
            t0 = time.time()
            current_video = _run_sadtalker(
                cfg,
                settings["sadtalker_dir"],
                audio_path,
                avatar_path,
                sadtalker_out,
                python_exe,
                settings["use_cuda"],
            )
            _log_timing("sadtalker_total", time.time() - t0)

            # TIMING: FFmpeg re-encode
            t0 = time.time()
            current_video = _reencode_h264(
                current_video,
                ffmpeg_path,
                Path(settings["musetalk_tmp_dir"]),
            )
            _log_timing("ffmpeg_encode", time.time() - t0)

            _log_timing("TOTAL", time.time() - t_total_start)
            
            # Print summary
            print("\n" + "="*50)
            print("TIMING SUMMARY:")
            for k, v in LAST_TIMINGS.items():
                pct = (v / LAST_TIMINGS.get("TOTAL", v)) * 100
                print(f"  {k}: {v:.2f}s ({pct:.1f}%)")
            print("="*50 + "\n")

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
    print("="*50)
    print("LIPSYNC Server with DETAILED TIMINGS")
    print("="*50)
    cfg = _load_config()
    host = _cfg_get(cfg, "lip_sync", "host", default="127.0.0.1")
    port = int(_cfg_get(cfg, "lip_sync", "port", default=7002))
    app.run(host=host, port=port, debug=False, threaded=True)
