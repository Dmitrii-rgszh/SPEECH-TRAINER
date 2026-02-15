"""
Minimal Flask test to isolate performance issue
"""
import time
import sys
import os

# Add SadTalker to path
SADTALKER_DIR = "E:/SPEECH TRAINER/CLEAN_AVATARS/PIPELINE/SadTalker"
sys.path.insert(0, SADTALKER_DIR)
os.chdir(SADTALKER_DIR)

from flask import Flask, request, send_file
from pathlib import Path
import io
import torch

print("Loading models...")
t0 = time.time()

from src.utils.preprocess import CropAndExtract
from src.test_audio2coeff import Audio2Coeff
from src.facerender.animate_optimized import AnimateFromCoeffOptimized
from src.utils.init_path import init_path
from src.generate_batch import get_data
from src.generate_facerender_batch import get_facerender_data

# Config
device = "cuda"
RESOLUTION = 256
EXPRESSION_SCALE = 0.3

# Init paths
sadtalker_paths = init_path(
    str(Path(SADTALKER_DIR) / "checkpoints"),
    str(Path(SADTALKER_DIR) / "src" / "config"),
    RESOLUTION,
    old_version=False,
    preprocess="crop"
)

# Load models
preprocess_model = CropAndExtract(sadtalker_paths, device)
audio_to_coeff = Audio2Coeff(sadtalker_paths, device)
animate_from_coeff = AnimateFromCoeffOptimized(sadtalker_paths, device, use_fp16=True)

# Precompute face
avatar_path = "E:/SPEECH TRAINER/CLEAN_AVATARS/MALE/Old_man/Male_55_yo.png"
output_dir = Path("E:/musetalk_tmp")
output_dir.mkdir(exist_ok=True)

first_frame_dir = output_dir / "first_frame_minimal"
first_frame_dir.mkdir(exist_ok=True)

first_coeff_path, crop_pic_path, crop_info = preprocess_model.generate(
    avatar_path, str(first_frame_dir), "crop",
    source_image_flag=True, pic_size=RESOLUTION
)

print(f"Models loaded in {time.time() - t0:.2f}s")

# Flask
app = Flask(__name__)

@app.route("/generate", methods=["POST"])
def generate():
    """Generate lip-sync video."""
    from time import strftime
    
    t_total = time.time()
    
    # Get audio
    audio_file = request.files.get("audio")
    if not audio_file:
        return {"error": "No audio"}, 400
    
    # Save audio
    audio_path = output_dir / f"input_{int(time.time()*1000)}.wav"
    audio_file.save(str(audio_path))
    
    try:
        # Create save dir
        save_dir = output_dir / strftime("%Y_%m_%d_%H.%M.%S")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Audio to coeff
        t0 = time.time()
        batch = get_data(first_coeff_path, str(audio_path), device, None, still=True)
        coeff_path = audio_to_coeff.generate(batch, str(save_dir), 0, ref_pose_coeff_path=None)
        print(f"  audio2coeff: {time.time()-t0:.2f}s")
        
        # Prepare data
        t0 = time.time()
        data = get_facerender_data(
            coeff_path, crop_pic_path, first_coeff_path, str(audio_path),
            1, None, None, None,
            expression_scale=EXPRESSION_SCALE, still_mode=True,
            preprocess="crop", size=RESOLUTION
        )
        print(f"  prepare_data: {time.time()-t0:.2f}s")
        
        # Generate video
        t0 = time.time()
        result_video = animate_from_coeff.generate(
            data, str(save_dir), None, crop_info,
            enhancer=None, background_enhancer=None,
            preprocess="crop", img_size=RESOLUTION,
            use_seamless_clone=False
        )
        print(f"  render: {time.time()-t0:.2f}s")
        
        print(f"TOTAL: {time.time()-t_total:.2f}s")
        
        # Read and return video
        video_data = Path(result_video).read_bytes()
        audio_path.unlink(missing_ok=True)
        
        return send_file(
            io.BytesIO(video_data),
            mimetype="video/mp4",
            as_attachment=False,
            download_name="lipsync.mp4"
        )
        
    except Exception as e:
        audio_path.unlink(missing_ok=True)
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

if __name__ == "__main__":
    print("\n" + "="*50)
    print("Minimal Test Server Ready")
    print(f"Resolution: {RESOLUTION}")
    print(f"Device: {device}")
    print("="*50 + "\n")
    
    app.run(host="0.0.0.0", port=7003, debug=False, threaded=False)
