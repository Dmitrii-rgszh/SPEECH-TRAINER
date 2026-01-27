from __future__ import annotations

import os
import tempfile
import threading
import time
import traceback
import webbrowser
import wave

from flask import Flask, jsonify, render_template, request
from faster_whisper import WhisperModel

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HF_HOME = os.path.join(BASE_DIR, ".cache", "hf")
DEFAULT_MODEL_DIR = os.path.join(BASE_DIR, ".cache", "whisper")
os.environ.setdefault("HF_HOME", DEFAULT_HF_HOME)

MODEL_SIZE = os.getenv("WHISPER_MODEL", "medium")
DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))

model = None
model_lock = threading.Lock()
model_device = None


def get_model():
    global model
    global model_device
    if model is None:
        with model_lock:
            if model is None:
                print("Loading Whisper model...", flush=True)
                try:
                    model = WhisperModel(
                        MODEL_SIZE,
                        device=DEVICE,
                        compute_type=COMPUTE_TYPE,
                        download_root=DEFAULT_MODEL_DIR,
                    )
                    model_device = DEVICE
                    print(f"Whisper model ready on {model_device}.", flush=True)
                except RuntimeError as exc:
                    msg = str(exc)
                    if "cublas" in msg.lower() or "cuda" in msg.lower():
                        print("CUDA runtime not found, falling back to CPU.", flush=True)
                        model = WhisperModel(
                            MODEL_SIZE,
                            device="cpu",
                            compute_type="int8",
                            download_root=DEFAULT_MODEL_DIR,
                        )
                        model_device = "cpu"
                        print("Whisper model ready on cpu.", flush=True)
                    else:
                        raise
    return model


@app.get("/")
def index():
    return render_template("index.html")


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/health")
def health():
    return jsonify({"status": "ok", "device": model_device or DEVICE})


@app.errorhandler(Exception)
def handle_error(error):
    print(traceback.format_exc(), flush=True)
    return jsonify({"error": str(error), "device": model_device or DEVICE}), 500


@app.post("/transcribe")
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "audio file is required"}), 400

    audio = request.files["audio"]
    if not audio.filename:
        return jsonify({"error": "empty filename"}), 400

    print("Transcribe request received", flush=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio.save(tmp.name)
            tmp_path = tmp.name

        audio_bytes = os.path.getsize(tmp_path)
        duration_sec = None
        try:
            with wave.open(tmp_path, "rb") as wav:
                duration_sec = wav.getnframes() / float(wav.getframerate())
        except wave.Error:
            pass

        print(
            f"Transcribe request: size={audio_bytes} bytes, duration={duration_sec}s",
            flush=True,
        )
        start_time = time.perf_counter()

        stt_model = get_model()
        segments, _info = stt_model.transcribe(
            tmp_path,
            language="ru",
            vad_filter=True,
            beam_size=BEAM_SIZE,
        )
        text = "".join(segment.text for segment in segments).strip()
        elapsed = time.perf_counter() - start_time
        print(f"Transcribe done in {elapsed:.2f}s", flush=True)
        return jsonify({"text": text, "device": model_device or DEVICE})
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    url = "http://127.0.0.1:5000"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    threading.Thread(target=get_model, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
