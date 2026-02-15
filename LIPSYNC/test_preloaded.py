"""
Test preloaded server performance
"""
import time
import sys
import os

# Add SadTalker to path
SADTALKER_DIR = "E:/SPEECH TRAINER/CLEAN_AVATARS/PIPELINE/SadTalker"
sys.path.insert(0, SADTALKER_DIR)
os.chdir(SADTALKER_DIR)

# Import pipeline components
print("="*60)
print("Test: Direct Pipeline (no server)")
print("="*60)

import torch
from src.utils.preprocess import CropAndExtract
from src.test_audio2coeff import Audio2Coeff
from src.facerender.animate_optimized import AnimateFromCoeffOptimized
from src.utils.init_path import init_path
from src.generate_batch import get_data
from src.generate_facerender_batch import get_facerender_data
from time import strftime
from pathlib import Path

device = "cuda"
RESOLUTION = 256  # 256 for speed (512 is 4x slower!)
EXPRESSION_SCALE = 0.3

# Load models ONCE
print("\n[1] Loading models...")
t0 = time.time()
sadtalker_paths = init_path(
    str(Path(SADTALKER_DIR) / "checkpoints"),
    str(Path(SADTALKER_DIR) / "src" / "config"),
    RESOLUTION,
    old_version=False,
    preprocess="crop"
)
preprocess_model = CropAndExtract(sadtalker_paths, device)
audio_to_coeff = Audio2Coeff(sadtalker_paths, device)
animate_from_coeff = AnimateFromCoeffOptimized(sadtalker_paths, device, use_fp16=True)
print(f"Models loaded in {time.time() - t0:.2f}s")

# Test paths
avatar_path = f"{SADTALKER_DIR}/examples/source_image/art_13.png"
audio_path = f"{SADTALKER_DIR}/examples/driven_audio/bus_chinese.wav"
output_dir = "E:/musetalk_tmp"

# Precompute face
print("\n[2] Precomputing face...")
t0 = time.time()
first_frame_dir = Path(output_dir) / "first_frame"
first_frame_dir.mkdir(parents=True, exist_ok=True)

first_coeff_path, crop_pic_path, crop_info = preprocess_model.generate(
    avatar_path, str(first_frame_dir), "crop",
    source_image_flag=True, pic_size=RESOLUTION
)
print(f"Face precomputed in {time.time() - t0:.2f}s")


def generate_video():
    """Single video generation - what server does per request"""
    save_dir = Path(output_dir) / strftime("%Y_%m_%d_%H.%M.%S")
    save_dir.mkdir(parents=True, exist_ok=True)
    
    t_total = time.time()
    
    # Audio to coeff
    t0 = time.time()
    batch = get_data(first_coeff_path, audio_path, device, None, still=True)
    coeff_path = audio_to_coeff.generate(batch, str(save_dir), 0, ref_pose_coeff_path=None)
    t_audio = time.time() - t0
    
    # Prepare data
    t0 = time.time()
    data = get_facerender_data(
        coeff_path, crop_pic_path, first_coeff_path, audio_path,
        1, None, None, None,
        expression_scale=EXPRESSION_SCALE, still_mode=True,
        preprocess="crop", size=RESOLUTION
    )
    t_data = time.time() - t0
    
    # Generate video
    t0 = time.time()
    result_video = animate_from_coeff.generate(
        data, str(save_dir), None, crop_info,
        enhancer=None, background_enhancer=None,
        preprocess="crop", img_size=RESOLUTION,
        use_seamless_clone=False
    )
    t_render = time.time() - t0
    
    t_total = time.time() - t_total
    
    print(f"  audio2coeff: {t_audio:.2f}s")
    print(f"  prepare_data: {t_data:.2f}s")
    print(f"  render: {t_render:.2f}s")
    print(f"  TOTAL: {t_total:.2f}s")
    
    return result_video, t_total


# Run multiple tests
print("\n" + "="*60)
print("TEST: Generate video 3 times (models in memory)")
print("="*60)

times = []
for i in range(3):
    print(f"\n--- Test {i+1} ---")
    result, elapsed = generate_video()
    times.append(elapsed)
    print(f"Result: {result}")

print("\n" + "="*60)
print(f"RESULTS: {', '.join(f'{t:.2f}s' for t in times)}")
print(f"Average: {sum(times)/len(times):.2f}s")
print("="*60)
