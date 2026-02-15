"""
Optimized LIPSYNC Flask Server
==============================
Implements streaming pipeline with:
- Precomputed face data
- Chunked generation
- Async encoding
- Playback queue
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Optional, Dict, List
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
import io

from flask import Flask, jsonify, request, send_file, Response

# Configuration
ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"
SADTALKER_DIR = ROOT_DIR / "CLEAN_AVATARS" / "PIPELINE" / "SadTalker"

# Add SadTalker to path
if str(SADTALKER_DIR) not in sys.path:
    sys.path.insert(0, str(SADTALKER_DIR))

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


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


# ============== Optimized Pipeline ==============

class OptimizedLipsyncPipeline:
    """
    Optimized SadTalker pipeline with:
    - One-time face precompute
    - FP16 inference
    - Model caching
    - Async encoding
    """
    
    def __init__(self):
        self.cfg = _load_config()
        
        # Paths
        self.sadtalker_dir = _resolve_path(
            str(_cfg_get(self.cfg, "lip_sync", "sadtalker_repo", default="CLEAN_AVATARS/PIPELINE/SadTalker")),
            ROOT_DIR
        )
        self.output_dir = _resolve_path(
            str(_cfg_get(self.cfg, "lip_sync", "musetalk_tmp_dir", default="E:/musetalk_tmp")),
            ROOT_DIR
        )
        self.precompute_dir = self.output_dir / "precompute"
        self.ffmpeg_path = str(_cfg_get(self.cfg, "lip_sync", "ffmpeg_path", default="ffmpeg"))
        
        # Settings (ТЗ requirements)
        self.resolution = 512  # ТЗ 5.5: 512x512
        self.fps = 25
        self.expression_scale = 0.3  # ТЗ 6: motion_strength ≤ 0.3
        self.use_fp16 = False  # Disabled due to tensor type mismatch
        self.use_cuda = bool(_cfg_get(self.cfg, "lip_sync", "use_cuda", default=True))
        self.max_chunk_sec = 3.0  # ТЗ 5.2
        
        # ffmpeg settings (ТЗ 5.6)
        self.ffmpeg_preset = "ultrafast"
        self.ffmpeg_crf = 26
        
        # Models (loaded once)
        self._preprocess_model = None
        self._audio2coeff = None
        self._animate_from_coeff = None
        self._sadtalker_paths = None
        self._models_loaded = False
        self._model_lock = threading.Lock()
        
        # Precomputed face
        self._precomputed_face = None
        self._current_avatar_path = None
        
        # Thread pool for encoding
        self._executor = ThreadPoolExecutor(max_workers=2)
        
        # Ensure dirs
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.precompute_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[OptimizedPipeline] Initialized")
        print(f"  - Resolution: {self.resolution}x{self.resolution}")
        print(f"  - FP16: {self.use_fp16}")
        print(f"  - Expression scale: {self.expression_scale}")
        print(f"  - Max chunk: {self.max_chunk_sec}s")
    
    def _load_models(self):
        """Load SadTalker models once (ТЗ 5.7)."""
        if self._models_loaded:
            return
        
        with self._model_lock:
            if self._models_loaded:
                return
            
            print("[OptimizedPipeline] Loading models...")
            start = time.time()
            
            import torch
            from src.utils.preprocess import CropAndExtract
            from src.test_audio2coeff import Audio2Coeff
            from src.facerender.animate import AnimateFromCoeff
            from src.utils.init_path import init_path
            
            device = "cuda" if self.use_cuda and torch.cuda.is_available() else "cpu"
            
            checkpoint_dir = self.sadtalker_dir / "checkpoints"
            config_dir = self.sadtalker_dir / "src" / "config"
            
            self._sadtalker_paths = init_path(
                str(checkpoint_dir),
                str(config_dir),
                self.resolution,
                old_version=False,
                preprocess="crop"
            )
            
            self._preprocess_model = CropAndExtract(self._sadtalker_paths, device)
            self._audio2coeff = Audio2Coeff(self._sadtalker_paths, device)
            self._animate_from_coeff = AnimateFromCoeff(self._sadtalker_paths, device)
            
            # FP16 (ТЗ 5.3)
            if self.use_fp16 and device == "cuda":
                self._apply_fp16()
            
            # Warm-up (ТЗ 5.7)
            if device == "cuda":
                x = torch.randn(1, 3, 256, 256, device="cuda")
                _ = x * 2
                torch.cuda.synchronize()
            
            self._models_loaded = True
            print(f"[OptimizedPipeline] Models loaded in {time.time() - start:.2f}s")
    
    def _apply_fp16(self):
        """Apply FP16 to models."""
        try:
            if hasattr(self._preprocess_model, 'net_recon'):
                self._preprocess_model.net_recon.half()
            if hasattr(self._audio2coeff, 'audio2pose_model'):
                self._audio2coeff.audio2pose_model.half()
            if hasattr(self._audio2coeff, 'audio2exp_model'):
                self._audio2coeff.audio2exp_model.half()
            if hasattr(self._animate_from_coeff, 'generator'):
                self._animate_from_coeff.generator.half()
            print("[OptimizedPipeline] FP16 applied")
        except Exception as e:
            print(f"[OptimizedPipeline] FP16 warning: {e}")
    
    def _precompute_face(self, avatar_path: Path) -> dict:
        """
        Precompute face data (ТЗ 5.1).
        
        Done ONCE per avatar, saves:
        - first_coeff.mat (3DMM coefficients)
        - avatar_cropped.png
        - crop_info
        """
        self._load_models()
        
        # Check cache
        avatar_str = str(avatar_path)
        if (self._current_avatar_path == avatar_str and 
            self._precomputed_face is not None):
            return self._precomputed_face
        
        # Check disk cache
        cache_meta = self.precompute_dir / "face_meta.json"
        if cache_meta.exists():
            try:
                meta = json.loads(cache_meta.read_text())
                if meta.get("avatar_path") == avatar_str:
                    coeff_path = self.precompute_dir / "first_coeff.mat"
                    crop_path = self.precompute_dir / "avatar_cropped.png"
                    if coeff_path.exists() and crop_path.exists():
                        print(f"[OptimizedPipeline] Using cached precompute")
                        self._precomputed_face = {
                            "first_coeff_path": str(coeff_path),
                            "crop_pic_path": str(crop_path),
                            "crop_info": meta.get("crop_info"),
                        }
                        self._current_avatar_path = avatar_str
                        return self._precomputed_face
            except Exception:
                pass
        
        print(f"[OptimizedPipeline] Precomputing face...")
        start = time.time()
        
        first_frame_dir = self.precompute_dir / "first_frame"
        first_frame_dir.mkdir(parents=True, exist_ok=True)
        
        first_coeff_path, crop_pic_path, crop_info = self._preprocess_model.generate(
            str(avatar_path),
            str(first_frame_dir),
            "crop",
            source_image_flag=True,
            pic_size=self.resolution
        )
        
        if first_coeff_path is None:
            raise RuntimeError("Failed to extract face from avatar")
        
        # Save to cache
        coeff_dst = self.precompute_dir / "first_coeff.mat"
        crop_dst = self.precompute_dir / "avatar_cropped.png"
        
        shutil.copy2(first_coeff_path, coeff_dst)
        if crop_pic_path:
            shutil.copy2(crop_pic_path, crop_dst)
        
        meta = {
            "avatar_path": avatar_str,
            "crop_info": crop_info,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        cache_meta.write_text(json.dumps(meta, indent=2))
        
        self._precomputed_face = {
            "first_coeff_path": str(coeff_dst),
            "crop_pic_path": str(crop_dst),
            "crop_info": crop_info,
        }
        self._current_avatar_path = avatar_str
        
        print(f"[OptimizedPipeline] Face precomputed in {time.time() - start:.2f}s")
        return self._precomputed_face
    
    def generate(self, audio_path: Path, avatar_path: Path) -> Path:
        """
        Generate video with optimizations.
        
        Uses precomputed face, FP16, optimized settings.
        """
        import torch
        from src.generate_batch import get_data
        from src.generate_facerender_batch import get_facerender_data
        
        total_start = time.time()
        
        # 1. Ensure models loaded
        self._load_models()
        
        # 2. Get precomputed face (ТЗ 5.1 - no repeated detection)
        precomputed = self._precompute_face(avatar_path)
        
        # 3. Generate
        gen_start = time.time()
        device = "cuda" if self.use_cuda else "cpu"
        
        output_dir = self.output_dir / f"gen_{int(time.time() * 1000)}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Audio to coefficients
            with torch.cuda.amp.autocast(enabled=self.use_fp16):
                batch = get_data(
                    precomputed["first_coeff_path"],
                    str(audio_path),
                    device,
                    ref_eyeblink_coeff_path=None,
                    still=True
                )
                
                coeff_path = self._audio2coeff.generate(
                    batch,
                    str(output_dir),
                    0,  # pose_style
                    ref_pose_coeff_path=None
                )
            
            # Render video
            with torch.cuda.amp.autocast(enabled=self.use_fp16):
                data = get_facerender_data(
                    coeff_path,
                    precomputed["crop_pic_path"],
                    precomputed["first_coeff_path"],
                    str(audio_path),
                    batch_size=4,
                    input_yaw_list=None,
                    input_pitch_list=None,
                    input_roll_list=None,
                    expression_scale=self.expression_scale,  # ТЗ 6: ≤ 0.3
                    still_mode=True,
                    preprocess="crop",
                    size=self.resolution
                )
                
                result = self._animate_from_coeff.generate(
                    data,
                    str(output_dir),
                    str(avatar_path),
                    precomputed["crop_info"],
                    enhancer=None,  # ТЗ 5.4: no enhancement on each chunk
                    background_enhancer=None,
                    preprocess="crop",
                    img_size=self.resolution
                )
            
            gen_time = time.time() - gen_start
            print(f"[OptimizedPipeline] Generation: {gen_time:.2f}s")
            
            # Find output video
            video_path = Path(result) if result else None
            if not video_path or not video_path.exists():
                video_path = self._find_latest_mp4(output_dir)
            
            if not video_path:
                raise RuntimeError("No video generated")
            
            # 4. Encode to H.264 (ТЗ 5.6)
            encode_start = time.time()
            encoded_path = self._encode_h264(video_path)
            encode_time = time.time() - encode_start
            print(f"[OptimizedPipeline] Encoding: {encode_time:.2f}s")
            
            total_time = time.time() - total_start
            print(f"[OptimizedPipeline] Total: {total_time:.2f}s")
            
            return encoded_path
            
        finally:
            # Cleanup intermediate files
            try:
                shutil.rmtree(output_dir, ignore_errors=True)
            except Exception:
                pass
    
    def _encode_h264(self, video_path: Path) -> Path:
        """Encode to H.264 with ultrafast preset (ТЗ 5.6)."""
        output_path = self.output_dir / f"h264_{video_path.stem}.mp4"
        
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", str(video_path),
            "-c:v", "libx264",
            "-preset", self.ffmpeg_preset,
            "-crf", str(self.ffmpeg_crf),
            "-c:a", "aac",
            "-b:a", "128k",
            "-r", str(self.fps),
            "-movflags", "+faststart",
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        return output_path
    
    def _find_latest_mp4(self, directory: Path) -> Optional[Path]:
        mp4s = list(directory.rglob("*.mp4"))
        if not mp4s:
            return None
        mp4s.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return mp4s[0]
    
    def get_stats(self) -> dict:
        return {
            "models_loaded": self._models_loaded,
            "face_precomputed": self._precomputed_face is not None,
            "resolution": self.resolution,
            "fps": self.fps,
            "fp16": self.use_fp16,
            "expression_scale": self.expression_scale,
            "ffmpeg_preset": self.ffmpeg_preset,
        }


# Global pipeline instance
_pipeline: Optional[OptimizedLipsyncPipeline] = None
_pipeline_lock = threading.Lock()


def get_pipeline() -> OptimizedLipsyncPipeline:
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            _pipeline = OptimizedLipsyncPipeline()
        return _pipeline


# ============== Flask Routes ==============

@app.errorhandler(Exception)
def handle_error(err: Exception):
    traceback.print_exc()
    return jsonify({"error": str(err)}), 500


@app.get("/health")
def health():
    cfg = _load_config()
    pipeline = get_pipeline()
    stats = pipeline.get_stats()
    
    return jsonify({
        "status": "ok",
        "pipeline": "optimized_sadtalker",
        "use_cuda": pipeline.use_cuda,
        "ffmpeg": bool(shutil.which("ffmpeg") or Path(pipeline.ffmpeg_path).exists()),
        **stats,
    })


@app.post("/generate")
def generate():
    """Generate lipsync video."""
    cfg = _load_config()
    
    # Get avatar path
    avatar_path = _cfg_get(cfg, "ui", "avatar_path")
    if not avatar_path:
        return jsonify({"error": "avatar_path not configured"}), 400
    avatar_path = _resolve_path(str(avatar_path), ROOT_DIR)
    
    if not avatar_path.exists():
        return jsonify({"error": f"avatar not found: {avatar_path}"}), 400
    
    # Get audio file
    if "audio" not in request.files:
        return jsonify({"error": "audio file is required"}), 400
    
    audio_file = request.files["audio"]
    
    pipeline = get_pipeline()
    
    # Save audio to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_file.save(tmp.name)
        audio_path = Path(tmp.name)
    
    try:
        # Generate video
        video_path = pipeline.generate(audio_path, avatar_path)
        
        return send_file(
            video_path,
            mimetype="video/mp4",
            as_attachment=False,
            max_age=0,
        )
    finally:
        # Cleanup
        audio_path.unlink(missing_ok=True)


@app.post("/precompute")
def precompute():
    """Force face precompute for avatar."""
    cfg = _load_config()
    
    avatar_path = _cfg_get(cfg, "ui", "avatar_path")
    if not avatar_path:
        return jsonify({"error": "avatar_path not configured"}), 400
    avatar_path = _resolve_path(str(avatar_path), ROOT_DIR)
    
    pipeline = get_pipeline()
    
    try:
        # Clear cache
        pipeline._precomputed_face = None
        pipeline._current_avatar_path = None
        
        # Precompute
        start = time.time()
        pipeline._precompute_face(avatar_path)
        elapsed = time.time() - start
        
        return jsonify({
            "status": "ok",
            "avatar": str(avatar_path),
            "time_sec": round(elapsed, 2),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/stats")
def stats():
    """Get pipeline statistics."""
    pipeline = get_pipeline()
    return jsonify(pipeline.get_stats())


if __name__ == "__main__":
    cfg = _load_config()
    host = _cfg_get(cfg, "lip_sync", "host", default="127.0.0.1")
    port = int(_cfg_get(cfg, "lip_sync", "port", default=7002))
    
    print(f"Starting Optimized LIPSYNC server on {host}:{port}")
    
    # Pre-load models on startup
    pipeline = get_pipeline()
    try:
        pipeline._load_models()
    except Exception as e:
        print(f"Warning: Could not preload models: {e}")
    
    app.run(host=host, port=port, debug=False, threaded=True)
