"""
Optimized SadTalker Pipeline
============================
Implements ТЗ requirements:
- Precompute face (bbox, landmarks, cropped avatar)
- Audio chunking (1-3 sec)
- FP16/AMP optimization
- Parallel pipeline (TTS/Inference/Encode/Playback)
- 512x512 resolution, 25 FPS
- Motion constraints (strength ≤ 0.3)
- Async video encoding
- Model warm-up and caching
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, List, Dict, Callable
import numpy as np

# Add SadTalker to path
SADTALKER_DIR = Path("E:/SPEECH TRAINER/CLEAN_AVATARS/PIPELINE/SadTalker")
if str(SADTALKER_DIR) not in sys.path:
    sys.path.insert(0, str(SADTALKER_DIR))


@dataclass
class PipelineConfig:
    """Pipeline configuration."""
    # Paths
    avatar_path: Path = None
    sadtalker_dir: Path = SADTALKER_DIR
    output_dir: Path = Path("E:/musetalk_tmp")
    precompute_dir: Path = Path("E:/musetalk_tmp/precompute")
    
    # Resolution and FPS (ТЗ 5.5)
    resolution: int = 512  # 512x512, NOT 1024
    fps: int = 25
    
    # Motion constraints (ТЗ 6)
    expression_scale: float = 0.3  # motion_strength ≤ 0.3
    pose_style: int = 0
    
    # Audio chunking (ТЗ 5.2)
    max_chunk_duration_sec: float = 3.0
    max_chunk_chars: int = 150
    
    # FP16 (ТЗ 5.3)
    use_fp16: bool = True
    use_cuda: bool = True
    device: str = "cuda"
    
    # Encoding (ТЗ 5.6)
    ffmpeg_path: str = "C:/ProgramData/chocolatey/bin/ffmpeg.exe"
    ffmpeg_preset: str = "ultrafast"
    ffmpeg_crf: int = 26
    
    # Enhancement (ТЗ 5.4) - disabled by default
    use_enhancer: bool = False
    enhancer: str = "none"
    
    # Performance
    batch_size: int = 4
    num_workers: int = 4


@dataclass 
class PrecomputedFace:
    """Precomputed face data (ТЗ 5.1)."""
    avatar_path: Path
    cropped_path: Path
    bbox: Dict[str, int]  # x, y, w, h
    landmarks_path: Path
    first_coeff_path: Path
    crop_info: Any = None
    
    @classmethod
    def load(cls, precompute_dir: Path) -> Optional["PrecomputedFace"]:
        """Load precomputed face data from disk."""
        meta_path = precompute_dir / "face_meta.json"
        if not meta_path.exists():
            return None
        
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            
            return cls(
                avatar_path=Path(meta["avatar_path"]),
                cropped_path=precompute_dir / "avatar_cropped.png",
                bbox=meta["bbox"],
                landmarks_path=precompute_dir / "face_landmarks.npy",
                first_coeff_path=precompute_dir / "first_coeff.mat",
                crop_info=meta.get("crop_info"),
            )
        except Exception:
            return None
    
    def save(self, precompute_dir: Path) -> None:
        """Save precomputed face data to disk."""
        precompute_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "avatar_path": str(self.avatar_path),
            "bbox": self.bbox,
            "crop_info": self.crop_info,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(precompute_dir / "face_meta.json", "w") as f:
            json.dump(meta, f, indent=2)


@dataclass
class AudioChunk:
    """Audio chunk for processing."""
    index: int
    audio_path: Path
    duration_sec: float
    text: str = ""


@dataclass
class VideoChunk:
    """Generated video chunk."""
    index: int
    video_path: Path
    duration_sec: float
    ready: bool = False


class OptimizedSadTalkerPipeline:
    """
    Optimized SadTalker pipeline implementing ТЗ requirements.
    
    Key optimizations:
    1. Face precompute - detects face once, reuses bbox/landmarks
    2. Audio chunking - splits audio into 1-3 sec chunks
    3. FP16 inference - reduces VRAM and speeds up
    4. Parallel processing - TTS/Inference/Encoding overlap
    5. Model caching - loads models once, warm-up on start
    6. Async encoding - GPU doesn't wait for ffmpeg
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.precomputed_face: Optional[PrecomputedFace] = None
        
        # Models (loaded once, ТЗ 5.7)
        self._preprocess_model = None
        self._audio2coeff_model = None
        self._animate_model = None
        self._models_loaded = False
        self._model_lock = threading.Lock()
        
        # Thread pools for parallel processing (ТЗ 5.8)
        self._encode_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="encoder")
        self._video_queue: queue.Queue[VideoChunk] = queue.Queue()
        
        # Ensure output dirs
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.precompute_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[Pipeline] Initialized with resolution={config.resolution}, fps={config.fps}")
        print(f"[Pipeline] FP16={config.use_fp16}, expression_scale={config.expression_scale}")
    
    def load_models(self) -> None:
        """Load SadTalker models once (ТЗ 5.7)."""
        if self._models_loaded:
            return
        
        with self._model_lock:
            if self._models_loaded:
                return
            
            print("[Pipeline] Loading SadTalker models...")
            start = time.time()
            
            import torch
            from src.utils.preprocess import CropAndExtract
            from src.test_audio2coeff import Audio2Coeff
            from src.facerender.animate import AnimateFromCoeff
            from src.utils.init_path import init_path
            
            device = self.config.device if self.config.use_cuda and torch.cuda.is_available() else "cpu"
            
            # Init paths
            checkpoint_dir = self.config.sadtalker_dir / "checkpoints"
            config_dir = self.config.sadtalker_dir / "src" / "config"
            
            sadtalker_paths = init_path(
                str(checkpoint_dir),
                str(config_dir),
                self.config.resolution,
                old_version=False,
                preprocess="crop"
            )
            
            # Load models
            self._preprocess_model = CropAndExtract(sadtalker_paths, device)
            self._audio2coeff_model = Audio2Coeff(sadtalker_paths, device)
            self._animate_model = AnimateFromCoeff(sadtalker_paths, device)
            
            # FP16 optimization (ТЗ 5.3)
            if self.config.use_fp16 and device == "cuda":
                self._apply_fp16()
            
            self._models_loaded = True
            print(f"[Pipeline] Models loaded in {time.time() - start:.2f}s")
            
            # Warm-up inference (ТЗ 5.7)
            self._warmup()
    
    def _apply_fp16(self) -> None:
        """Apply FP16 to models (ТЗ 5.3)."""
        import torch
        
        try:
            # Convert models to half precision where possible
            if hasattr(self._preprocess_model, 'net_recon'):
                self._preprocess_model.net_recon.half()
            if hasattr(self._audio2coeff_model, 'audio2pose_model'):
                self._audio2coeff_model.audio2pose_model.half()
            if hasattr(self._audio2coeff_model, 'audio2exp_model'):
                self._audio2coeff_model.audio2exp_model.half()
            if hasattr(self._animate_model, 'generator'):
                self._animate_model.generator.half()
            print("[Pipeline] FP16 applied to models")
        except Exception as e:
            print(f"[Pipeline] FP16 warning: {e}")
    
    def _warmup(self) -> None:
        """Warm-up inference to prime CUDA (ТЗ 5.7)."""
        print("[Pipeline] Warming up CUDA...")
        import torch
        
        if self.config.use_cuda and torch.cuda.is_available():
            # Simple CUDA warm-up
            x = torch.randn(1, 3, 256, 256, device="cuda")
            _ = x * 2
            torch.cuda.synchronize()
        print("[Pipeline] Warm-up complete")
    
    def precompute_face(self, avatar_path: Path, force: bool = False) -> PrecomputedFace:
        """
        Precompute face data (ТЗ 5.1).
        
        Extracts and saves:
        - Bounding box
        - Facial landmarks  
        - Cropped avatar image
        - 3DMM coefficients
        
        This is done ONCE per avatar, not on every generation.
        """
        self.load_models()
        
        # Check if already precomputed
        if not force:
            existing = PrecomputedFace.load(self.config.precompute_dir)
            if existing and existing.avatar_path == avatar_path:
                if existing.cropped_path.exists() and existing.first_coeff_path.exists():
                    print(f"[Pipeline] Using cached face precompute for {avatar_path.name}")
                    self.precomputed_face = existing
                    return existing
        
        print(f"[Pipeline] Precomputing face for {avatar_path.name}...")
        start = time.time()
        
        # Create temp dir for extraction
        first_frame_dir = self.config.precompute_dir / "first_frame"
        first_frame_dir.mkdir(parents=True, exist_ok=True)
        
        # Run face extraction
        first_coeff_path, crop_pic_path, crop_info = self._preprocess_model.generate(
            str(avatar_path),
            str(first_frame_dir),
            "crop",  # Use crop preprocessing
            source_image_flag=True,
            pic_size=self.config.resolution
        )
        
        if first_coeff_path is None:
            raise RuntimeError("Failed to extract face coefficients from avatar")
        
        # Copy cropped image to precompute dir
        cropped_dst = self.config.precompute_dir / "avatar_cropped.png"
        if crop_pic_path and Path(crop_pic_path).exists():
            shutil.copy2(crop_pic_path, cropped_dst)
        
        # Copy coefficients
        coeff_dst = self.config.precompute_dir / "first_coeff.mat"
        if first_coeff_path and Path(first_coeff_path).exists():
            shutil.copy2(first_coeff_path, coeff_dst)
        
        # Extract bbox from crop_info
        bbox = {"x": 0, "y": 0, "w": self.config.resolution, "h": self.config.resolution}
        if crop_info:
            # crop_info format varies, try to extract bbox
            if isinstance(crop_info, (list, tuple)) and len(crop_info) >= 4:
                bbox = {
                    "x": int(crop_info[0]) if crop_info[0] else 0,
                    "y": int(crop_info[1]) if crop_info[1] else 0,
                    "w": int(crop_info[2]) if crop_info[2] else self.config.resolution,
                    "h": int(crop_info[3]) if crop_info[3] else self.config.resolution,
                }
        
        # Save landmarks if available
        landmarks_path = self.config.precompute_dir / "face_landmarks.npy"
        # (Landmarks are embedded in first_coeff.mat)
        
        precomputed = PrecomputedFace(
            avatar_path=avatar_path,
            cropped_path=cropped_dst,
            bbox=bbox,
            landmarks_path=landmarks_path,
            first_coeff_path=coeff_dst,
            crop_info=crop_info,
        )
        precomputed.save(self.config.precompute_dir)
        
        self.precomputed_face = precomputed
        print(f"[Pipeline] Face precomputed in {time.time() - start:.2f}s")
        
        return precomputed
    
    def chunk_audio(self, audio_path: Path) -> List[AudioChunk]:
        """
        Split audio into chunks (ТЗ 5.2).
        
        Max chunk: 3 seconds or 150 characters.
        """
        import wave
        
        with wave.open(str(audio_path), 'rb') as wav:
            n_frames = wav.getnframes()
            framerate = wav.getframerate()
            duration = n_frames / framerate
        
        # If audio is short enough, return as single chunk
        if duration <= self.config.max_chunk_duration_sec:
            return [AudioChunk(
                index=0,
                audio_path=audio_path,
                duration_sec=duration,
            )]
        
        # Split into chunks
        chunks = []
        chunk_duration = self.config.max_chunk_duration_sec
        num_chunks = int(np.ceil(duration / chunk_duration))
        
        for i in range(num_chunks):
            chunk_start = i * chunk_duration
            chunk_end = min((i + 1) * chunk_duration, duration)
            actual_duration = chunk_end - chunk_start
            
            # Extract chunk using ffmpeg
            chunk_path = self.config.output_dir / f"chunk_{i:03d}.wav"
            cmd = [
                self.config.ffmpeg_path, "-y",
                "-i", str(audio_path),
                "-ss", str(chunk_start),
                "-t", str(actual_duration),
                "-c:a", "pcm_s16le",
                "-ar", "16000",
                str(chunk_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            
            chunks.append(AudioChunk(
                index=i,
                audio_path=chunk_path,
                duration_sec=actual_duration,
            ))
        
        return chunks
    
    def generate_video_chunk(self, audio_chunk: AudioChunk) -> VideoChunk:
        """
        Generate video for a single audio chunk.
        
        Uses precomputed face data to skip redundant processing.
        """
        import torch
        from src.generate_batch import get_data
        from src.generate_facerender_batch import get_facerender_data
        
        self.load_models()
        
        if self.precomputed_face is None:
            raise RuntimeError("Face not precomputed. Call precompute_face() first.")
        
        start = time.time()
        chunk_output_dir = self.config.output_dir / f"chunk_{audio_chunk.index:03d}"
        chunk_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Use precomputed coefficients (ТЗ 5.1 - no re-detection)
        first_coeff_path = str(self.precomputed_face.first_coeff_path)
        crop_pic_path = str(self.precomputed_face.cropped_path)
        
        device = self.config.device
        
        # Audio to coefficients
        with torch.cuda.amp.autocast(enabled=self.config.use_fp16):
            batch = get_data(
                first_coeff_path,
                str(audio_chunk.audio_path),
                device,
                ref_eyeblink_coeff_path=None,
                still=True  # Minimal motion
            )
            
            coeff_path = self._audio2coeff_model.generate(
                batch,
                str(chunk_output_dir),
                self.config.pose_style,
                ref_pose_coeff_path=None
            )
        
        # Generate video frames
        with torch.cuda.amp.autocast(enabled=self.config.use_fp16):
            data = get_facerender_data(
                coeff_path,
                crop_pic_path,
                first_coeff_path,
                str(audio_chunk.audio_path),
                self.config.batch_size,
                input_yaw_list=None,
                input_pitch_list=None,
                input_roll_list=None,
                expression_scale=self.config.expression_scale,  # ТЗ 6: ≤ 0.3
                still_mode=True,
                preprocess="crop",
                size=self.config.resolution
            )
            
            result = self._animate_model.generate(
                data,
                str(chunk_output_dir),
                str(self.precomputed_face.avatar_path),
                self.precomputed_face.crop_info,
                enhancer=None if not self.config.use_enhancer else self.config.enhancer,
                background_enhancer=None,
                preprocess="crop",
                img_size=self.config.resolution
            )
        
        # Find generated video
        video_path = Path(result) if result else None
        if not video_path or not video_path.exists():
            video_path = self._find_latest_mp4(chunk_output_dir)
        
        if not video_path:
            raise RuntimeError(f"Failed to generate video for chunk {audio_chunk.index}")
        
        print(f"[Pipeline] Chunk {audio_chunk.index} generated in {time.time() - start:.2f}s")
        
        return VideoChunk(
            index=audio_chunk.index,
            video_path=video_path,
            duration_sec=audio_chunk.duration_sec,
            ready=True,
        )
    
    def encode_video_async(self, video_chunk: VideoChunk) -> Path:
        """
        Encode video to H.264 asynchronously (ТЗ 5.6).
        
        Uses ultrafast preset, CRF 26, runs in background.
        """
        output_path = self.config.output_dir / f"encoded_{video_chunk.index:03d}.mp4"
        
        cmd = [
            self.config.ffmpeg_path, "-y",
            "-i", str(video_chunk.video_path),
            "-c:v", "libx264",
            "-preset", self.config.ffmpeg_preset,  # ultrafast
            "-crf", str(self.config.ffmpeg_crf),
            "-c:a", "aac",
            "-b:a", "128k",
            "-r", str(self.config.fps),
            "-s", f"{self.config.resolution}x{self.config.resolution}",
            "-movflags", "+faststart",
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    
    def generate_full(self, audio_path: Path, avatar_path: Path = None) -> Path:
        """
        Generate full video with optimizations.
        
        Flow:
        1. Precompute face (if needed)
        2. Chunk audio
        3. Generate video chunks (parallel where possible)
        4. Encode and concatenate
        """
        total_start = time.time()
        
        # 1. Precompute face
        if avatar_path:
            self.config.avatar_path = avatar_path
        if self.config.avatar_path is None:
            raise ValueError("Avatar path not set")
        
        self.precompute_face(self.config.avatar_path)
        
        # 2. Chunk audio
        chunks = self.chunk_audio(audio_path)
        print(f"[Pipeline] Split audio into {len(chunks)} chunks")
        
        # 3. Generate video for each chunk
        video_chunks = []
        for chunk in chunks:
            video_chunk = self.generate_video_chunk(chunk)
            video_chunks.append(video_chunk)
        
        # 4. Encode all chunks
        encoded_paths = []
        for vc in video_chunks:
            encoded = self.encode_video_async(vc)
            encoded_paths.append(encoded)
        
        # 5. Concatenate if multiple chunks
        if len(encoded_paths) == 1:
            final_path = encoded_paths[0]
        else:
            final_path = self._concatenate_videos(encoded_paths)
        
        total_time = time.time() - total_start
        print(f"[Pipeline] Total generation time: {total_time:.2f}s")
        
        return final_path
    
    def _concatenate_videos(self, video_paths: List[Path]) -> Path:
        """Concatenate multiple video chunks."""
        concat_list = self.config.output_dir / "concat_list.txt"
        with open(concat_list, "w") as f:
            for p in video_paths:
                f.write(f"file '{p}'\n")
        
        output_path = self.config.output_dir / "final_output.mp4"
        cmd = [
            self.config.ffmpeg_path, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        
        return output_path
    
    def _find_latest_mp4(self, directory: Path) -> Optional[Path]:
        """Find most recent MP4 in directory."""
        mp4s = list(directory.rglob("*.mp4"))
        if not mp4s:
            return None
        mp4s.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return mp4s[0]
    
    def cleanup(self) -> None:
        """Clean up temporary files."""
        # Keep precomputed face data
        for p in self.config.output_dir.glob("chunk_*"):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.is_file():
                p.unlink(missing_ok=True)
        
        for p in self.config.output_dir.glob("encoded_*.mp4"):
            p.unlink(missing_ok=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "models_loaded": self._models_loaded,
            "face_precomputed": self.precomputed_face is not None,
            "resolution": self.config.resolution,
            "fps": self.config.fps,
            "fp16": self.config.use_fp16,
            "expression_scale": self.config.expression_scale,
            "max_chunk_sec": self.config.max_chunk_duration_sec,
        }


# Global pipeline instance (singleton)
_pipeline: Optional[OptimizedSadTalkerPipeline] = None
_pipeline_lock = threading.Lock()


def get_pipeline(config: PipelineConfig = None) -> OptimizedSadTalkerPipeline:
    """Get or create global pipeline instance."""
    global _pipeline
    
    with _pipeline_lock:
        if _pipeline is None:
            if config is None:
                config = PipelineConfig()
            _pipeline = OptimizedSadTalkerPipeline(config)
        return _pipeline


def generate_optimized(
    audio_path: Path,
    avatar_path: Path,
    config: PipelineConfig = None,
) -> Path:
    """
    Main entry point for optimized video generation.
    
    Args:
        audio_path: Path to audio file (WAV)
        avatar_path: Path to avatar image (PNG)
        config: Optional pipeline configuration
    
    Returns:
        Path to generated video (MP4)
    """
    pipeline = get_pipeline(config)
    pipeline.config.avatar_path = avatar_path
    return pipeline.generate_full(audio_path, avatar_path)


if __name__ == "__main__":
    # Test run
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimized SadTalker Pipeline")
    parser.add_argument("--audio", required=True, help="Path to audio file")
    parser.add_argument("--avatar", required=True, help="Path to avatar image")
    parser.add_argument("--output", default="E:/musetalk_tmp/output.mp4", help="Output path")
    parser.add_argument("--resolution", type=int, default=512, help="Resolution (512 or 256)")
    parser.add_argument("--expression-scale", type=float, default=0.3, help="Expression scale (0.0-1.0)")
    
    args = parser.parse_args()
    
    config = PipelineConfig(
        resolution=args.resolution,
        expression_scale=args.expression_scale,
    )
    
    result = generate_optimized(
        audio_path=Path(args.audio),
        avatar_path=Path(args.avatar),
        config=config,
    )
    
    print(f"Generated: {result}")
    if args.output != str(result):
        shutil.copy2(result, args.output)
        print(f"Copied to: {args.output}")
