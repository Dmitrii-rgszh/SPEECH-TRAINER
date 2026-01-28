from __future__ import annotations

import io
import json
import os
import subprocess
import threading
import wave
from pathlib import Path

import numpy as np
import onnxruntime as ort
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _env_or(cfg: dict, env_key: str, cfg_key: str, default=None):
    env_val = os.getenv(env_key)
    if env_val is not None and env_val != "":
        return env_val
    if isinstance(cfg, dict) and cfg_key in cfg:
        return cfg.get(cfg_key)
    return default


def _default_phonemize_paths() -> tuple[str, str]:
    base = Path(__file__).resolve().parent / "piper-phonemize" / "piper-phonemize"
    exe = base / "bin" / "piper_phonemize_exe.exe"
    data = base / "share" / "espeak-ng-data"
    return (str(exe) if exe.exists() else "", str(data) if data.exists() else "")


def voice_settings(cfg: dict) -> dict:
    vg = cfg.get("voice_generator", {}) if isinstance(cfg.get("voice_generator"), dict) else {}
    host = str(_env_or(vg, "TTS_HOST", "host", "127.0.0.1"))
    port = int(_env_or(vg, "TTS_PORT", "port", 7001))
    model_path = str(_env_or(vg, "PIPER_MODEL_PATH", "model_path", ""))
    config_path = str(_env_or(vg, "PIPER_CONFIG_PATH", "config_path", ""))
    phonemize_exe = str(_env_or(vg, "PIPER_PHONEMIZE_EXE", "phonemize_exe", ""))
    espeak_data = str(_env_or(vg, "PIPER_ESPEAK_DATA", "espeak_data", ""))
    use_cuda = _env_or(vg, "PIPER_USE_CUDA", "use_cuda", False)
    speaker_id = _env_or(vg, "PIPER_SPEAKER_ID", "speaker_id", 0)
    length_scale = _env_or(vg, "PIPER_LENGTH_SCALE", "length_scale", 1.0)
    noise_scale = _env_or(vg, "PIPER_NOISE_SCALE", "noise_scale", 0.667)
    noise_w = _env_or(vg, "PIPER_NOISE_W", "noise_w", 0.8)

    if not phonemize_exe or not espeak_data:
        default_exe, default_data = _default_phonemize_paths()
        if not phonemize_exe:
            phonemize_exe = default_exe
        if not espeak_data:
            espeak_data = default_data

    return {
        "host": host,
        "port": port,
        "model_path": model_path,
        "config_path": config_path,
        "phonemize_exe": phonemize_exe,
        "espeak_data": espeak_data,
        "use_cuda": (str(use_cuda).strip().lower() in {"1", "true", "yes", "on"}),
        "speaker_id": int(speaker_id) if str(speaker_id).strip() else 0,
        "length_scale": float(length_scale),
        "noise_scale": float(noise_scale),
        "noise_w": float(noise_w),
    }


CONFIG = load_config()
VOICE = voice_settings(CONFIG)

_voice_lock = threading.Lock()
_voice = None


def resolve_config_path(model_path: str, config_path: str) -> str:
    if config_path and Path(config_path).exists():
        return config_path
    if model_path:
        direct = Path(model_path + ".json")
        if direct.exists():
            return str(direct)
        alt = Path(model_path).with_suffix(Path(model_path).suffix + ".json")
        if alt.exists():
            return str(alt)
        onnx_json = Path(model_path).with_suffix(".onnx.json")
        if onnx_json.exists():
            return str(onnx_json)
    return config_path


class PiperRuntime:
    def __init__(self, model_path: str, config_path: str, phonemize_exe: str, espeak_data: str) -> None:
        self.model_path = model_path
        self.config_path = config_path
        self.phonemize_exe = phonemize_exe
        self.espeak_data = espeak_data

        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.sample_rate = int(cfg.get("audio", {}).get("sample_rate", 22050))
        self.num_speakers = int(cfg.get("num_speakers", 1))
        self.espeak_voice = str(cfg.get("espeak", {}).get("voice", "")) or "ru"
        inference = cfg.get("inference", {}) or {}
        self.default_length_scale = float(inference.get("length_scale", 1.0))
        self.default_noise_scale = float(inference.get("noise_scale", 0.667))
        self.default_noise_w = float(inference.get("noise_w", 0.8))

        providers = ["CPUExecutionProvider"]
        if VOICE.get("use_cuda"):
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(model_path, providers=providers)

    def phonemize(self, text: str) -> list[int]:
        if not self.phonemize_exe or not Path(self.phonemize_exe).exists():
            raise RuntimeError("PIPER_PHONEMIZE_EXE не найден (piper_phonemize_exe.exe)")
        if not self.espeak_data or not Path(self.espeak_data).exists():
            raise RuntimeError("PIPER_ESPEAK_DATA не найден (espeak-ng-data)")

        cmd = [
            self.phonemize_exe,
            "-l",
            self.espeak_voice,
            "--espeak_data",
            self.espeak_data,
            "--allow_missing_phonemes",
        ]
        proc = subprocess.run(
            cmd,
            input=(text.strip() + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", errors="ignore") or "phonemize failed")

        output = proc.stdout.decode("utf-8", errors="ignore").strip()
        if not output:
            raise RuntimeError("phonemize output is empty")

        line = output.splitlines()[0]
        data = json.loads(line)
        ids = data.get("phoneme_ids")
        if not isinstance(ids, list) or not ids:
            raise RuntimeError("phoneme_ids not found in phonemize output")
        return [int(x) for x in ids]

    def synthesize(self, text: str, speaker_id: int, length_scale: float, noise_scale: float, noise_w: float) -> np.ndarray:
        phoneme_ids = self.phonemize(text)
        phoneme_ids_array = np.expand_dims(np.array(phoneme_ids, dtype=np.int64), 0)
        phoneme_ids_lengths = np.array([phoneme_ids_array.shape[1]], dtype=np.int64)
        scales = np.array([noise_scale, length_scale, noise_w], dtype=np.float32)

        args = {
            "input": phoneme_ids_array,
            "input_lengths": phoneme_ids_lengths,
            "scales": scales,
        }

        if self.num_speakers > 1:
            args["sid"] = np.array([int(speaker_id)], dtype=np.int64)

        audio = self.session.run(None, args)[0].squeeze((0, 1))
        audio = np.clip(audio, -1.0, 1.0)
        return (audio * 32767.0).astype(np.int16)


def get_voice() -> PiperRuntime:
    global _voice
    if _voice is not None:
        return _voice
    model_path = VOICE["model_path"]
    if not model_path:
        raise RuntimeError("PIPER_MODEL_PATH не задан (config.json -> voice_generator.model_path)")
    config_path = resolve_config_path(model_path, VOICE["config_path"])
    if not config_path or not Path(config_path).exists():
        raise RuntimeError("Файл конфигурации модели Piper не найден")

    with _voice_lock:
        if _voice is None:
            _voice = PiperRuntime(
                model_path=model_path,
                config_path=config_path,
                phonemize_exe=VOICE["phonemize_exe"],
                espeak_data=VOICE["espeak_data"],
            )
    return _voice


def synthesize_wav_bytes(text: str, speaker_id: int, length_scale: float, noise_scale: float, noise_w: float) -> io.BytesIO:
    voice = get_voice()
    audio = voice.synthesize(
        text,
        speaker_id=speaker_id,
        length_scale=length_scale,
        noise_scale=noise_scale,
        noise_w=noise_w,
    )

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(voice.sample_rate)
        wav.writeframes(audio.tobytes())
    buf.seek(0)
    return buf


def normalize_tts_text(text: str) -> str:
    cleaned = text.replace("\r", " ").replace("\n", " ")
    # strip common markdown artifacts
    for token in ("**", "__", "*", "`", "#", "---"):
        cleaned = cleaned.replace(token, " ")
    # remove bullet/numbering artifacts
    cleaned = cleaned.replace("•", " ")
    cleaned = cleaned.replace("- ", " ")
    cleaned = cleaned.replace("-", " ")
    # collapse whitespace
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


@app.get("/health")
def health():
    ok = True
    error = ""
    try:
        _ = get_voice()
    except Exception as exc:
        ok = False
        error = str(exc)

    return jsonify(
        {
            "status": "ok" if ok else "error",
            "model_path": VOICE.get("model_path"),
            "config_path": VOICE.get("config_path"),
            "phonemize_exe": VOICE.get("phonemize_exe"),
            "espeak_data": VOICE.get("espeak_data"),
            "speaker_id": VOICE.get("speaker_id"),
            "error": error,
        }
    )


@app.post("/speak")
def speak():
    data = request.get_json(silent=True) or {}
    text = normalize_tts_text((data.get("text") or "").strip())
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        speaker_id = int(data.get("speaker_id", VOICE["speaker_id"]))
        length_scale = float(data.get("length_scale", VOICE["length_scale"]))
        noise_scale = float(data.get("noise_scale", VOICE["noise_scale"]))
        noise_w = float(data.get("noise_w", VOICE["noise_w"]))
        wav_buf = synthesize_wav_bytes(text, speaker_id, length_scale, noise_scale, noise_w)
        return send_file(wav_buf, mimetype="audio/wav", as_attachment=False, download_name="speech.wav")
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    host = VOICE["host"]
    port = VOICE["port"]
    print(f"VOICE_GENERATOR on http://{host}:{port}", flush=True)
    app.run(host=host, port=port, debug=False, use_reloader=False)
