"""
Optimized LIPSYNC Server with Persistent Worker
================================================
Flask server that communicates with long-running SadTalker worker process.
Models stay loaded in worker memory for fast inference.
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
import threading
from pathlib import Path
from typing import Any, Optional
import io

from flask import Flask, jsonify, request, send_file

# Configuration
ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"
WORKER_SCRIPT = Path(__file__).parent / "sadtalker_worker.py"

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


# ============== Worker Manager ==============

class WorkerManager:
    """Manages long-running SadTalker worker process."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.ready = False
        self.lock = threading.Lock()
        self._face_precomputed = False
    
    def start(self, python_exe: str) -> bool:
        """Start worker process."""
        with self.lock:
            if self.process and self.process.poll() is None:
                return True  # Already running
            
            print("[Manager] Starting worker...")
            
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            env["HF_HUB_DISABLE_SAFE_WEIGHTS"] = "1"
            
            try:
                self.process = subprocess.Popen(
                    [python_exe, str(WORKER_SCRIPT)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    bufsize=1,  # Line buffered
                )
                
                # Wait for ready signal
                line = self.process.stdout.readline()
                resp = json.loads(line.strip())
                if resp.get("status") == "ready":
                    self.ready = True
                    print("[Manager] Worker ready")
                    return True
                
            except Exception as e:
                print(f"[Manager] Failed to start: {e}")
                traceback.print_exc()
        
        return False
    
    def stop(self):
        """Stop worker process."""
        with self.lock:
            if self.process:
                try:
                    self._send_command({"action": "quit"}, timeout=2)
                except:
                    pass
                self.process.terminate()
                self.process = None
                self.ready = False
                self._face_precomputed = False
    
    def _send_command(self, cmd: dict, timeout: float = 300) -> dict:
        """Send command to worker and get response."""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("Worker not running")
        
        self.process.stdin.write(json.dumps(cmd) + "\n")
        self.process.stdin.flush()
        
        # Read response with timeout (simplified - no real timeout here)
        line = self.process.stdout.readline()
        if not line:
            # Check stderr for error
            stderr = self.process.stderr.read()
            raise RuntimeError(f"Worker died: {stderr}")
        
        return json.loads(line.strip())
    
    def precompute_face(self, avatar_path: str, output_dir: str) -> dict:
        """Precompute face data for avatar."""
        resp = self._send_command({
            "action": "precompute",
            "avatar_path": avatar_path,
            "output_dir": output_dir,
        })
        if resp.get("status") == "ok":
            self._face_precomputed = True
        return resp
    
    def generate(
        self,
        audio_path: str,
        avatar_path: str,
        output_dir: str,
        expression_scale: float = 0.3,
    ) -> str:
        """Generate lip-sync video."""
        resp = self._send_command({
            "action": "generate",
            "audio_path": audio_path,
            "avatar_path": avatar_path,
            "output_dir": output_dir,
            "expression_scale": expression_scale,
        })
        
        if resp.get("status") != "ok":
            raise RuntimeError(resp.get("error", "Unknown error"))
        
        return resp["video_path"]
    
    @property
    def is_ready(self) -> bool:
        return self.ready and self.process and self.process.poll() is None
    
    @property
    def face_precomputed(self) -> bool:
        return self._face_precomputed


# Global worker manager
worker_mgr = WorkerManager()


# ============== Optimized Settings ==============

class OptimizedSettings:
    """Settings per ТЗ."""
    RESOLUTION = 512
    EXPRESSION_SCALE = 0.3
    FFMPEG_PRESET = "ultrafast"
    FFMPEG_CRF = 26


# ============== H.264 Encoding ==============

def _reencode_h264(input_path: Path, ffmpeg_path: str, output_dir: Path) -> Path:
    """Re-encode to H.264 with ultrafast preset."""
    output_path = output_dir / f"h264_{input_path.name}"
    
    cmd = [
        ffmpeg_path, "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", OptimizedSettings.FFMPEG_PRESET,
        "-crf", str(OptimizedSettings.FFMPEG_CRF),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        if output_path.exists():
            return output_path
    except Exception as e:
        print(f"[Server] Encoding warning: {e}")
    
    return input_path


# ============== Flask Routes ==============

@app.route("/health", methods=["GET"])
def health():
    cfg = _load_config()
    ffmpeg = _ffmpeg_path(cfg)
    
    return jsonify({
        "status": "ok",
        "pipeline": "optimized_worker",
        "worker_ready": worker_mgr.is_ready,
        "face_precomputed": worker_mgr.face_precomputed,
        "resolution": OptimizedSettings.RESOLUTION,
        "expression_scale": OptimizedSettings.EXPRESSION_SCALE,
        "ffmpeg_preset": OptimizedSettings.FFMPEG_PRESET,
        "ffmpeg": bool(ffmpeg),
    })


@app.route("/precompute", methods=["POST"])
def precompute():
    """Precompute face data for current avatar."""
    cfg = _load_config()
    avatar_path = _get_avatar_path(cfg)
    
    if not avatar_path or not avatar_path.exists():
        return jsonify({"error": "Avatar not configured"}), 400
    
    output_dir = _resolve_path(
        str(_cfg_get(cfg, "lip_sync", "musetalk_tmp_dir", default="E:/musetalk_tmp")),
        ROOT_DIR
    )
    _ensure_dir(output_dir)
    
    try:
        result = worker_mgr.precompute_face(str(avatar_path), str(output_dir))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate", methods=["POST"])
def generate():
    """Generate lip-sync video."""
    start_total = time.time()
    
    cfg = _load_config()
    
    # Check worker
    if not worker_mgr.is_ready:
        return jsonify({"error": "Worker not ready"}), 503
    
    # Get audio
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400
    
    audio_file = request.files["audio"]
    
    # Get avatar
    avatar_path = _get_avatar_path(cfg)
    if not avatar_path or not avatar_path.exists():
        return jsonify({"error": "Avatar not configured"}), 400
    
    # Output directory
    output_dir = _resolve_path(
        str(_cfg_get(cfg, "lip_sync", "musetalk_tmp_dir", default="E:/musetalk_tmp")),
        ROOT_DIR
    )
    _ensure_dir(output_dir)
    
    # Save audio to temp file
    audio_path = output_dir / f"input_{int(time.time()*1000)}.wav"
    audio_file.save(str(audio_path))
    
    try:
        # Generate video
        print(f"[Server] Generating...")
        video_path = worker_mgr.generate(
            audio_path=str(audio_path),
            avatar_path=str(avatar_path),
            output_dir=str(output_dir),
            expression_scale=OptimizedSettings.EXPRESSION_SCALE,
        )
        
        # Re-encode to H.264
        ffmpeg = _ffmpeg_path(cfg)
        if ffmpeg:
            video_path = _reencode_h264(Path(video_path), ffmpeg, output_dir)
        
        elapsed = time.time() - start_total
        print(f"[Server] Total: {elapsed:.2f}s")
        
        # Read video into memory
        video_data = Path(video_path).read_bytes()
        
        # Cleanup temp audio
        audio_path.unlink(missing_ok=True)
        
        return send_file(
            io.BytesIO(video_data),
            mimetype="video/mp4",
            as_attachment=False,
            download_name="lipsync.mp4"
        )
    
    except Exception as e:
        audio_path.unlink(missing_ok=True)
        _log_error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ============== Startup ==============

def init_worker():
    """Initialize worker process."""
    cfg = _load_config()
    python_exe = str(_cfg_get(cfg, "lip_sync", "python_exe", default=sys.executable))
    
    if not worker_mgr.start(python_exe):
        print("[Server] WARNING: Failed to start worker!")
        return
    
    # Precompute face for default avatar
    avatar_path = _get_avatar_path(cfg)
    if avatar_path and avatar_path.exists():
        output_dir = _resolve_path(
            str(_cfg_get(cfg, "lip_sync", "musetalk_tmp_dir", default="E:/musetalk_tmp")),
            ROOT_DIR
        )
        _ensure_dir(output_dir)
        
        try:
            worker_mgr.precompute_face(str(avatar_path), str(output_dir))
            print("[Server] Face precomputed")
        except Exception as e:
            print(f"[Server] Face precompute failed: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("Optimized LIPSYNC Server (Worker)")
    print("=" * 50)
    
    init_worker()
    
    print("=" * 50)
    print(f"Worker ready: {worker_mgr.is_ready}")
    print(f"Face precomputed: {worker_mgr.face_precomputed}")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=7002, debug=False, threaded=True)
