from __future__ import annotations

import io
import os
import shutil
import threading
import time
import traceback
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from PIL import Image

from pipeline.ffmpeg_encode import encode
from pipeline.liveportrait_runner import run_liveportrait
from pipeline.utils import OUTPUT_DIR, TEMP_DIR, audio_duration_sec, ensure_dir, timestamp_id
from pipeline.wav2lip_runner import run_wav2lip

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Keep HuggingFace cache on E: drive
os.environ.setdefault(
    "HF_HOME",
    str((Path(__file__).resolve().parent / "hf_cache").resolve()),
)

_shared_py = Path(__file__).resolve().parents[1] / "LIPSYNC" / ".venv" / "Scripts" / "python.exe"
if _shared_py.exists():
    os.environ.setdefault("LIVEPORTRAIT_PYTHON", str(_shared_py))
    os.environ.setdefault("WAV2LIP_PYTHON", str(_shared_py))

_gan_ckpt = Path(__file__).resolve().parent / "models" / "wav2lip" / "checkpoints" / "wav2lip_gan.pth"
if _gan_ckpt.exists():
    os.environ["WAV2LIP_CHECKPOINT"] = str(_gan_ckpt)
os.environ["WAV2LIP_USE_BOX"] = "1"
os.environ["WAV2LIP_INPROCESS"] = "1"


def _save_rgb_image(upload, out_path: Path) -> None:
    image = Image.open(upload.stream)
    image = image.convert("RGB")
    image.save(out_path)


def _save_audio(upload, out_path: Path) -> None:
    with open(out_path, "wb") as f:
        shutil.copyfileobj(upload.stream, f)


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/generate")
def generate():
    if "image" not in request.files:
        return jsonify({"error": "image file is required"}), 400
    if "audio" not in request.files:
        return jsonify({"error": "audio file is required"}), 400

    image_file = request.files["image"]
    audio_file = request.files["audio"]

    if not image_file.filename:
        return jsonify({"error": "empty image filename"}), 400
    if not audio_file.filename:
        return jsonify({"error": "empty audio filename"}), 400

    preview = str(request.args.get("preview", "false")).lower() in {"1", "true", "yes"}

    ensure_dir(TEMP_DIR)
    ensure_dir(OUTPUT_DIR)

    job_id = timestamp_id("talk")
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        image_path = job_dir / "source.png"
        audio_ext = Path(audio_file.filename).suffix or ".wav"
        audio_path = job_dir / f"audio{audio_ext}"

        _save_rgb_image(image_file, image_path)
        _save_audio(audio_file, audio_path)

        duration = audio_duration_sec(audio_path)
        target_duration = max(0.5, duration + 0.5)

        base_video = job_dir / "base.mp4"
        t0 = time.perf_counter()
        _log(f"{job_id} LivePortrait start (duration={target_duration:.2f}s)")
        run_liveportrait(str(image_path), target_duration, str(base_video))
        _log(f"{job_id} LivePortrait done in {time.perf_counter() - t0:.2f}s")
        if not base_video.exists():
            raise RuntimeError("LivePortrait did not produce base.mp4")

        if preview:
            return send_file(str(base_video), mimetype="video/mp4", as_attachment=False)

        lipsynced_video = job_dir / "lipsynced.mp4"
        t1 = time.perf_counter()
        _log(f"{job_id} Wav2Lip start")
        run_wav2lip(str(base_video), str(audio_path), str(lipsynced_video))
        _log(f"{job_id} Wav2Lip done in {time.perf_counter() - t1:.2f}s")
        if not lipsynced_video.exists():
            raise RuntimeError("Wav2Lip did not produce lipsynced.mp4")

        output_video = OUTPUT_DIR / f"{job_id}.mp4"
        t2 = time.perf_counter()
        encode(str(lipsynced_video), str(output_video))
        _log(f"{job_id} Encode done in {time.perf_counter() - t2:.2f}s")

        return send_file(str(output_video), mimetype="video/mp4", as_attachment=False)
    except Exception as exc:
        _log(f"{job_id} Error: {exc}")
        _log(traceback.format_exc())
        return jsonify({"error": str(exc)}), 500
    finally:
        keep_temp = os.getenv("KEEP_TEMP", "0") in {"1", "true", "yes"}
        if not keep_temp:
            try:
                shutil.rmtree(job_dir)
            except Exception:
                pass


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "7011"))

    def _prewarm() -> None:
        prewarm = os.getenv("LIVEPORTRAIT_PREWARM", "0").lower() in {"1", "true", "yes"}
        prewarm_wav2lip = os.getenv("LIVEPORTRAIT_PREWARM_WAV2LIP", "0").lower() in {"1", "true", "yes"}
        image = os.getenv("LIVEPORTRAIT_PREWARM_IMAGE", "")
        if not prewarm or not image:
            return
        image_path = Path(image).expanduser()
        if not image_path.exists():
            _log(f"Prewarm skipped (image not found): {image_path}")
            return
        duration = float(os.getenv("LIVEPORTRAIT_PREWARM_SECONDS", "12"))
        try:
            _log(f"Prewarm start (duration={duration:.2f}s, image={image_path})")
            tmp_out = OUTPUT_DIR / "prewarm_base.mp4"
            run_liveportrait(str(image_path), duration, str(tmp_out))
            if not prewarm_wav2lip:
                _log("Prewarm done (LivePortrait only)")
                try:
                    tmp_out.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            tmp_wav = OUTPUT_DIR / "prewarm_silence.wav"
            import wave

            sample_rate = 16000
            silence_sec = 1.0
            total_frames = int(sample_rate * silence_sec)
            with wave.open(str(tmp_wav), "wb") as wav_f:
                wav_f.setnchannels(1)
                wav_f.setsampwidth(2)
                wav_f.setframerate(sample_rate)
                wav_f.writeframes(b"\x00\x00" * total_frames)
            tmp_lip = OUTPUT_DIR / "prewarm_lipsync.mp4"
            _log("Prewarm Wav2Lip start")
            run_wav2lip(str(tmp_out), str(tmp_wav), str(tmp_lip))
            _log("Prewarm Wav2Lip done")
            try:
                tmp_wav.unlink(missing_ok=True)
                tmp_lip.unlink(missing_ok=True)
                tmp_out.unlink(missing_ok=True)
            except Exception:
                pass
            _log("Prewarm done")
        except Exception as exc:
            _log(f"Prewarm failed: {exc}")

    threading.Thread(target=_prewarm, daemon=True).start()
    app.run(host=host, port=port, debug=False, threaded=True)
