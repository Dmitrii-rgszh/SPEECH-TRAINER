"""
LIPSYNC Server with Preloaded Models
=====================================
Flask server with SadTalker models loaded at startup.
Keeps models in memory for fast inference.

Settings:
- Resolution 512 (original quality)
- AnimateFromCoeff (original, no FP16)
- Models preloaded in memory
- Face data cached

Performance: ~90s per video (original quality)
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

# Setup SadTalker path BEFORE flask import
SADTALKER_DIR = Path(__file__).resolve().parents[1] / "CLEAN_AVATARS" / "PIPELINE" / "SadTalker"
sys.path.insert(0, str(SADTALKER_DIR))
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["HF_HUB_DISABLE_SAFE_WEIGHTS"] = "1"

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


# ============== SadTalker Pipeline ==============

class SadTalkerPipeline:
    """SadTalker with models kept in memory."""
    
    # Quality settings - 512 for better lip sync quality
    RESOLUTION = 512
    EXPRESSION_SCALE = 0.3
    FFMPEG_PRESET = "ultrafast"
    FFMPEG_CRF = 26
    
    def __init__(self):
        self.models_loaded = False
        self.face_cache = {}  # avatar_path -> face data
        self._lock = threading.Lock()
        
        # Will be set after load_models()
        self.preprocess_model = None
        self.audio_to_coeff = None
        self.animate_from_coeff = None
        self.sadtalker_paths = None
        self.device = "cpu"
    
    def load_models(self, use_cuda: bool = True):
        """Load SadTalker models (call once at startup)."""
        if self.models_loaded:
            return
        
        with self._lock:
            if self.models_loaded:
                return
            
            print("[Pipeline] Loading models...")
            start = time.time()
            
            import torch
            from time import strftime
            from src.utils.preprocess import CropAndExtract
            from src.test_audio2coeff import Audio2Coeff
            from src.facerender.animate import AnimateFromCoeff
            from src.utils.init_path import init_path
            
            self.device = "cuda" if use_cuda and torch.cuda.is_available() else "cpu"
            
            checkpoint_dir = SADTALKER_DIR / "checkpoints"
            config_dir = SADTALKER_DIR / "src" / "config"
            
            self.sadtalker_paths = init_path(
                str(checkpoint_dir),
                str(config_dir),
                self.RESOLUTION,
                old_version=False,
                preprocess="crop"
            )
            
            self.preprocess_model = CropAndExtract(self.sadtalker_paths, self.device)
            self.audio_to_coeff = Audio2Coeff(self.sadtalker_paths, self.device)
            self.animate_from_coeff = AnimateFromCoeff(
                self.sadtalker_paths, self.device
            )
            
            # Warm up GPU
            if self.device == "cuda":
                x = torch.randn(1, 3, 256, 256, device="cuda")
                _ = x * 2
                torch.cuda.synchronize()
            
            self.models_loaded = True
            print(f"[Pipeline] Models loaded in {time.time() - start:.2f}s on {self.device}")
    
    def precompute_face(self, avatar_path: str, output_dir: str) -> dict:
        """Precompute face data (done once per avatar)."""
        
        # Check cache
        if avatar_path in self.face_cache:
            return {"cached": True, **self.face_cache[avatar_path]}
        
        first_frame_dir = Path(output_dir) / "first_frame_dir"
        first_frame_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[Pipeline] Extracting face...")
        start = time.time()
        
        first_coeff_path, crop_pic_path, crop_info = self.preprocess_model.generate(
            avatar_path, str(first_frame_dir), "crop",
            source_image_flag=True, pic_size=self.RESOLUTION
        )
        
        if first_coeff_path is None:
            raise RuntimeError("Failed to extract face coefficients")
        
        result = {
            "first_coeff_path": str(first_coeff_path),
            "crop_pic_path": str(crop_pic_path),
            "crop_info": crop_info,
        }
        
        self.face_cache[avatar_path] = result
        print(f"[Pipeline] Face extracted in {time.time() - start:.2f}s")
        
        return {"cached": False, **result}
    
    def generate(self, audio_path: str, avatar_path: str, output_dir: str) -> str:
        """Generate lip-sync video (thread-safe, one at a time)."""
        with self._lock:  # Только один запрос одновременно
            return self._generate_impl(audio_path, avatar_path, output_dir)
    
    def _generate_impl(self, audio_path: str, avatar_path: str, output_dir: str) -> str:
        """Generate lip-sync video implementation."""
        from time import strftime
        from src.generate_batch import get_data
        from src.generate_facerender_batch import get_facerender_data
        
        save_dir = Path(output_dir) / strftime("%Y_%m_%d_%H.%M.%S")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Get or compute face data
        face_data = self.precompute_face(avatar_path, str(save_dir))
        first_coeff_path = face_data["first_coeff_path"]
        crop_pic_path = face_data["crop_pic_path"]
        crop_info = face_data["crop_info"]
        
        print(f"[Pipeline] Generating...")
        start = time.time()
        
        # Audio to coefficients
        batch = get_data(first_coeff_path, audio_path, self.device, None, still=True)
        coeff_path = self.audio_to_coeff.generate(
            batch, str(save_dir), 0, ref_pose_coeff_path=None
        )
        
        # Generate video - use "crop" preprocess for speed
        data = get_facerender_data(
            coeff_path, crop_pic_path, first_coeff_path, audio_path,
            1, None, None, None,  # batch_size, yaw, pitch, roll
            expression_scale=self.EXPRESSION_SCALE, still_mode=True, 
            preprocess="crop", size=self.RESOLUTION
        )
        
        result_video = self.animate_from_coeff.generate(
            data, str(save_dir), None, crop_info,
            enhancer=None, background_enhancer=None,
            preprocess="crop", img_size=self.RESOLUTION
        )
        
        print(f"[Pipeline] Generated in {time.time() - start:.2f}s")
        
        return result_video


# Global pipeline
pipeline = SadTalkerPipeline()


# ============== H.264 Encoding ==============

def _reencode_h264(input_path: Path, ffmpeg_path: str, output_dir: Path) -> Path:
    """Re-encode to H.264 with ultrafast preset."""
    output_path = output_dir / f"h264_{input_path.name}"
    
    cmd = [
        ffmpeg_path, "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", SadTalkerPipeline.FFMPEG_PRESET,
        "-crf", str(SadTalkerPipeline.FFMPEG_CRF),
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
        "pipeline": "optimized_preloaded",
        "models_loaded": pipeline.models_loaded,
        "device": pipeline.device,
        "face_cached": len(pipeline.face_cache),
        "resolution": SadTalkerPipeline.RESOLUTION,
        "expression_scale": SadTalkerPipeline.EXPRESSION_SCALE,
        "ffmpeg_preset": SadTalkerPipeline.FFMPEG_PRESET,
        "ffmpeg": bool(ffmpeg),
    })


@app.route("/precompute", methods=["POST"])
def precompute():
    """Precompute face data for current avatar."""
    if not pipeline.models_loaded:
        return jsonify({"error": "Models not loaded"}), 503
    
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
        result = pipeline.precompute_face(str(avatar_path), str(output_dir))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate", methods=["POST"])
def generate():
    """Generate lip-sync video."""
    start_total = time.time()
    
    if not pipeline.models_loaded:
        return jsonify({"error": "Models not loaded"}), 503
    
    cfg = _load_config()
    
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
        video_path = pipeline.generate(
            audio_path=str(audio_path),
            avatar_path=str(avatar_path),
            output_dir=str(output_dir),
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

if __name__ == "__main__":
    print("=" * 50)
    print("Optimized LIPSYNC Server (Preloaded)")
    print("=" * 50)
    
    cfg = _load_config()
    use_cuda = bool(_cfg_get(cfg, "lip_sync", "use_cuda", default=True))
    
    # Load models at startup
    pipeline.load_models(use_cuda=use_cuda)
    
    # Precompute face for default avatar
    avatar_path = _get_avatar_path(cfg)
    if avatar_path and avatar_path.exists():
        output_dir = _resolve_path(
            str(_cfg_get(cfg, "lip_sync", "musetalk_tmp_dir", default="E:/musetalk_tmp")),
            ROOT_DIR
        )
        _ensure_dir(output_dir)
        
        try:
            pipeline.precompute_face(str(avatar_path), str(output_dir))
            print("[Server] Face precomputed")
        except Exception as e:
            print(f"[Server] Face precompute failed: {e}")
    
    print("=" * 50)
    print(f"Models loaded: {pipeline.models_loaded}")
    print(f"Device: {pipeline.device}")
    print(f"Faces cached: {len(pipeline.face_cache)}")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=7002, debug=False, threaded=True)
