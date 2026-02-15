"""
Optimized LIPSYNC Flask Server (Subprocess Version)
====================================================
Uses subprocess calls to SadTalker inference.py with optimized settings.
Compatible with .venv environment.
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

# Configuration
ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


# ============== Logging ==============

def _log_error(message: str) -> None:
    try:
        err_path = ROOT_DIR / "LIPSYNC" / "error.log"
        with open(err_path, "a", encoding="utf-8") as f:
            f.write("\n" + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write(message + "\n")
    except Exception:
        pass


@app.errorhandler(Exception)
def handle_error(err: Exception):
    _log_error(traceback.format_exc())
    return jsonify({"error": str(err)}), 500


# ============== Configuration ==============

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


# ============== Optimized Settings ==============

class OptimizedSettings:
    """Optimized settings per ТЗ."""
    
    # ТЗ 5.5: resolution 512x512
    RESOLUTION = 512
    
    # ТЗ 6: expression_scale / motion_strength ≤ 0.3
    EXPRESSION_SCALE = 0.3
    
    # ТЗ 5.6: ffmpeg ultrafast
    FFMPEG_PRESET = "ultrafast"
    FFMPEG_CRF = 26
    
    # FPS target
    FPS = 25


# ============== SadTalker Runner ==============

def _get_sadtalker_python() -> str:
    """Get Python executable for SadTalker (sadtalker conda env)."""
    cfg = _load_config()
    
    # Check config first
    python_exe = _cfg_get(cfg, "lip_sync", "python_exe")
    if python_exe:
        return str(python_exe)
    
    # Try conda sadtalker env
    conda_base = Path(os.environ.get("CONDA_PREFIX", "")).parent
    if conda_base.exists():
        sadtalker_python = conda_base / "envs" / "sadtalker" / "python.exe"
        if sadtalker_python.exists():
            return str(sadtalker_python)
    
    # Fallback paths
    for path in [
        Path(r"C:\Users\shapeless\miniconda3\envs\sadtalker\python.exe"),
        Path(r"E:\miniconda3\envs\sadtalker\python.exe"),
    ]:
        if path.exists():
            return str(path)
    
    # Use current Python
    return sys.executable


def _get_avatar_path(cfg: dict[str, Any]) -> Optional[Path]:
    avatar = _cfg_get(cfg, "ui", "avatar_path")
    if not avatar:
        return None
    return _resolve_path(str(avatar), ROOT_DIR)


def _ffmpeg_path(cfg: dict[str, Any]) -> Optional[str]:
    value = _cfg_get(cfg, "lip_sync", "ffmpeg_path")
    if value:
        return str(_resolve_path(str(value), ROOT_DIR))
    return shutil.which("ffmpeg")


def _run_sadtalker_optimized(
    audio_path: Path,
    avatar_path: Path,
    output_dir: Path,
) -> Path:
    """
    Run SadTalker with optimized settings.
    
    Uses:
    - 512x512 resolution (ТЗ 5.5)
    - expression_scale 0.3 (ТЗ 6)
    - No enhancer for speed
    """
    cfg = _load_config()
    
    sadtalker_dir = _resolve_path(
        str(_cfg_get(cfg, "lip_sync", "sadtalker_repo", default="CLEAN_AVATARS/PIPELINE/SadTalker")),
        ROOT_DIR
    )
    
    if not sadtalker_dir.exists():
        raise FileNotFoundError(f"SadTalker not found at {sadtalker_dir}")
    
    python_exe = _get_sadtalker_python()
    _ensure_dir(output_dir)
    
    # Build command with optimized parameters
    cmd = [
        python_exe,
        "inference.py",
        "--driven_audio", str(audio_path),
        "--source_image", str(avatar_path),
        "--result_dir", str(output_dir),
        "--still",
        "--preprocess", "full",
        "--size", str(OptimizedSettings.RESOLUTION),  # 512
        "--expression_scale", str(OptimizedSettings.EXPRESSION_SCALE),  # 0.3
        # No enhancer for speed
    ]
    
    print(f"[Optimized] Running SadTalker: {' '.join(cmd)}")
    start = time.time()
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("HF_HUB_DISABLE_SAFE_WEIGHTS", "1")
    
    proc = subprocess.run(
        cmd,
        cwd=str(sadtalker_dir),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    
    elapsed = time.time() - start
    print(f"[Optimized] SadTalker done in {elapsed:.2f}s")
    
    if proc.returncode != 0:
        _log_error(f"SadTalker error:\n{proc.stdout}\n{proc.stderr}")
        raise RuntimeError(f"SadTalker failed:\n{proc.stdout[-2000:]}")
    
    result = _pick_latest_mp4(output_dir)
    if not result:
        raise RuntimeError("SadTalker did not produce output video")
    
    return result


def _reencode_h264_optimized(input_path: Path, ffmpeg_path: str, output_dir: Path) -> Path:
    """
    Re-encode to H.264 with ultrafast preset (ТЗ 5.6).
    """
    output_path = output_dir / f"h264_{input_path.name}"
    
    cmd = [
        ffmpeg_path, "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", OptimizedSettings.FFMPEG_PRESET,  # ultrafast
        "-crf", str(OptimizedSettings.FFMPEG_CRF),   # 26
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    print(f"[Optimized] Encoding H.264: preset={OptimizedSettings.FFMPEG_PRESET}, crf={OptimizedSettings.FFMPEG_CRF}")
    start = time.time()
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        print(f"[Optimized] Encoding done in {time.time() - start:.2f}s")
        if output_path.exists():
            return output_path
    except Exception as e:
        print(f"[Optimized] Encoding warning: {e}")
    
    return input_path


# ============== Flask Routes ==============

@app.route("/health", methods=["GET"])
def health():
    cfg = _load_config()
    ffmpeg = _ffmpeg_path(cfg)
    
    return jsonify({
        "status": "ok",
        "pipeline": "optimized_sadtalker_subprocess",
        "resolution": OptimizedSettings.RESOLUTION,
        "expression_scale": OptimizedSettings.EXPRESSION_SCALE,
        "ffmpeg_preset": OptimizedSettings.FFMPEG_PRESET,
        "ffmpeg": bool(ffmpeg),
        "sadtalker_python": _get_sadtalker_python(),
    })


@app.route("/generate", methods=["POST"])
def generate():
    """Generate lip-sync video with optimized settings."""
    start_total = time.time()
    
    cfg = _load_config()
    
    # Get audio
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    audio_file = request.files["audio"]
    
    # Get avatar
    avatar_path = _get_avatar_path(cfg)
    if not avatar_path or not avatar_path.exists():
        return jsonify({"error": "Avatar not configured or missing"}), 400
    
    # Create temp dir
    output_dir = _resolve_path(
        str(_cfg_get(cfg, "lip_sync", "musetalk_tmp_dir", default="E:/musetalk_tmp")),
        ROOT_DIR
    )
    _ensure_dir(output_dir)
    
    with tempfile.TemporaryDirectory(dir=str(output_dir)) as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Save audio
        audio_path = tmp_path / "input.wav"
        audio_file.save(str(audio_path))
        print(f"[Optimized] Audio saved: {audio_path}")
        
        # Run SadTalker
        sadtalker_output = tmp_path / "sadtalker_out"
        raw_video = _run_sadtalker_optimized(audio_path, avatar_path, sadtalker_output)
        
        # Re-encode to H.264
        ffmpeg = _ffmpeg_path(cfg)
        if ffmpeg:
            final_video = _reencode_h264_optimized(raw_video, ffmpeg, tmp_path)
        else:
            final_video = raw_video
        
        elapsed = time.time() - start_total
        print(f"[Optimized] Total time: {elapsed:.2f}s")
        
        # Read video into memory before temp dir is deleted
        import io
        video_data = final_video.read_bytes()
        video_buffer = io.BytesIO(video_data)
        
        # Return video from memory
        return send_file(
            video_buffer,
            mimetype="video/mp4",
            as_attachment=False,
            download_name="lipsync.mp4"
        )


if __name__ == "__main__":
    print("=" * 50)
    print("Optimized LIPSYNC Server (Subprocess)")
    print("=" * 50)
    print(f"Resolution: {OptimizedSettings.RESOLUTION}x{OptimizedSettings.RESOLUTION}")
    print(f"Expression scale: {OptimizedSettings.EXPRESSION_SCALE}")
    print(f"FFmpeg preset: {OptimizedSettings.FFMPEG_PRESET}")
    print(f"SadTalker Python: {_get_sadtalker_python()}")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=7002, debug=False, threaded=True)
