"""
SadTalker Worker Process
========================
Long-running worker that keeps models loaded in memory.
Accepts generation requests via stdin, returns video path.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

# Configure paths
SADTALKER_DIR = Path(__file__).resolve().parents[1] / "CLEAN_AVATARS" / "PIPELINE" / "SadTalker"
sys.path.insert(0, str(SADTALKER_DIR))

# Suppress warnings
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["HF_HUB_DISABLE_SAFE_WEIGHTS"] = "1"

import torch
from time import strftime

from src.utils.preprocess import CropAndExtract
from src.test_audio2coeff import Audio2Coeff
from src.facerender.animate import AnimateFromCoeff
from src.generate_batch import get_data
from src.generate_facerender_batch import get_facerender_data
from src.utils.init_path import init_path

class SadTalkerWorker:
    """Keep SadTalker models loaded for fast inference."""
    
    def __init__(self, size: int = 512, use_cuda: bool = True):
        self.size = size
        self.device = "cuda" if use_cuda and torch.cuda.is_available() else "cpu"
        
        # Redirect stderr temporarily to capture any import noise
        import io as _io
        old_stderr = sys.stderr
        sys.stderr = _io.StringIO()
        
        try:
            checkpoint_dir = SADTALKER_DIR / "checkpoints"
            config_dir = SADTALKER_DIR / "src" / "config"
            
            self.sadtalker_paths = init_path(
                str(checkpoint_dir),
                str(config_dir),
                size,
                old_version=False,
                preprocess="crop"
            )
            
            self.preprocess_model = CropAndExtract(self.sadtalker_paths, self.device)
            self.audio_to_coeff = Audio2Coeff(self.sadtalker_paths, self.device)
            self.animate_from_coeff = AnimateFromCoeff(self.sadtalker_paths, self.device)
            
            # Precomputed face data
            self._face_cache = {}
            
            # Warm up
            if self.device == "cuda":
                x = torch.randn(1, 3, 256, 256, device="cuda")
                _ = x * 2
                torch.cuda.synchronize()
        finally:
            sys.stderr = old_stderr
    
    def precompute_face(self, avatar_path: str, output_dir: str) -> dict:
        """Precompute face data for avatar (done once per avatar)."""
        
        # Check cache
        if avatar_path in self._face_cache:
            data = self._face_cache[avatar_path]
            return {"cached": True, **data}
        
        first_frame_dir = Path(output_dir) / "first_frame_dir"
        first_frame_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[Worker] Extracting face from {avatar_path}...", file=sys.stderr)
        start = time.time()
        
        first_coeff_path, crop_pic_path, crop_info = self.preprocess_model.generate(
            avatar_path, str(first_frame_dir), "crop",
            source_image_flag=True, pic_size=self.size
        )
        
        if first_coeff_path is None:
            raise RuntimeError("Failed to extract face coefficients")
        
        result = {
            "first_coeff_path": str(first_coeff_path),
            "crop_pic_path": str(crop_pic_path),
            "crop_info": crop_info,
        }
        
        self._face_cache[avatar_path] = result
        print(f"[Worker] Face extracted in {time.time() - start:.2f}s", file=sys.stderr)
        
        return {"cached": False, **result}
    
    def generate(
        self,
        audio_path: str,
        avatar_path: str,
        output_dir: str,
        expression_scale: float = 0.3,
    ) -> str:
        """Generate lip-sync video."""
        
        save_dir = Path(output_dir) / strftime("%Y_%m_%d_%H.%M.%S")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Get or compute face data
        face_data = self.precompute_face(avatar_path, str(save_dir))
        first_coeff_path = face_data["first_coeff_path"]
        crop_pic_path = face_data["crop_pic_path"]
        crop_info = face_data["crop_info"]
        
        print(f"[Worker] Generating for {audio_path}...", file=sys.stderr)
        start = time.time()
        
        # Audio to coefficients
        batch = get_data(first_coeff_path, audio_path, self.device, None, still=True)
        coeff_path = self.audio_to_coeff.generate(
            batch, str(save_dir), 0, ref_pose_coeff_path=None
        )
        
        # Generate video
        data = get_facerender_data(
            coeff_path, crop_pic_path, first_coeff_path, audio_path,
            1, expression_scale=expression_scale, still=True, preprocess="crop", size=self.size
        )
        
        result_video = self.animate_from_coeff.generate(
            data, str(save_dir), None, crop_info,
            enhancer=None, background_enhancer=None,
            preprocess="crop", img_size=self.size
        )
        
        print(f"[Worker] Done in {time.time() - start:.2f}s", file=sys.stderr)
        
        return result_video


def main():
    """Main loop - read JSON commands from stdin, write responses to stdout."""
    
    # Initialize worker
    worker = SadTalkerWorker(size=512, use_cuda=True)
    
    # Signal ready
    print(json.dumps({"status": "ready"}), flush=True)
    
    # Command loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            cmd = json.loads(line)
            action = cmd.get("action")
            
            if action == "generate":
                video_path = worker.generate(
                    audio_path=cmd["audio_path"],
                    avatar_path=cmd["avatar_path"],
                    output_dir=cmd["output_dir"],
                    expression_scale=cmd.get("expression_scale", 0.3),
                )
                print(json.dumps({"status": "ok", "video_path": video_path}), flush=True)
            
            elif action == "precompute":
                face_data = worker.precompute_face(
                    avatar_path=cmd["avatar_path"],
                    output_dir=cmd["output_dir"],
                )
                print(json.dumps({"status": "ok", **face_data}), flush=True)
            
            elif action == "ping":
                print(json.dumps({"status": "pong"}), flush=True)
            
            elif action == "quit":
                print(json.dumps({"status": "bye"}), flush=True)
                break
            
            else:
                print(json.dumps({"status": "error", "error": f"Unknown action: {action}"}), flush=True)
        
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({"status": "error", "error": str(e)}), flush=True)


if __name__ == "__main__":
    main()
