from __future__ import annotations

import io
import json
import os
import shutil
import threading
import wave
from pathlib import Path

import numpy as np
import torch
from flask import Flask, jsonify, request, send_file

# XTTS-v2 requires ToS acknowledgement for first download.
os.environ.setdefault("COQUI_TOS_AGREED", "1")

from TTS.api import TTS

app = Flask(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"
VG_DIR = Path(__file__).resolve().parent

# Force all Coqui/HF caches to stay inside VOICE_GENERATOR (no C: fallback).
os.environ.setdefault("TTS_HOME", str(VG_DIR))
os.environ.setdefault("HF_HOME", str(VG_DIR / ".hf_home"))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(VG_DIR / ".hf_home" / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(VG_DIR / ".hf_home" / "transformers"))


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


def voice_settings(cfg: dict) -> dict:
    vg = cfg.get("voice_generator", {}) if isinstance(cfg.get("voice_generator"), dict) else {}
    host = str(_env_or(vg, "TTS_HOST", "host", "127.0.0.1"))
    port = int(_env_or(vg, "TTS_PORT", "port", 7001))
    model_name = str(
        _env_or(vg, "XTTS_MODEL_NAME", "model_name", "tts_models/multilingual/multi-dataset/xtts_v2")
    )
    model_dir = str(_env_or(vg, "XTTS_MODEL_DIR", "model_dir", str(VG_DIR / "XTTS-v2")))
    use_cuda = _env_or(vg, "XTTS_USE_CUDA", "use_cuda", True)
    language = str(_env_or(vg, "XTTS_LANGUAGE", "language", "ru"))
    reference_wav = str(_env_or(vg, "XTTS_REFERENCE_WAV", "reference_wav", ""))
    speaker = str(_env_or(vg, "XTTS_SPEAKER", "speaker", ""))

    return {
        "host": host,
        "port": port,
        "model_name": model_name,
        "model_dir": model_dir,
        "use_cuda": (str(use_cuda).strip().lower() in {"1", "true", "yes", "on"}),
        "language": language.strip() or "ru",
        "reference_wav": reference_wav,
        "speaker": speaker,
    }


CONFIG = load_config()
VOICE = voice_settings(CONFIG)

_voice_lock = threading.Lock()
_synth_lock = threading.Lock()
_voice = None


class XttsRuntime:
    def __init__(self, model_name: str, model_dir: str, use_cuda: bool) -> None:
        self.model_name = model_name
        self.device = "cuda" if (use_cuda and torch.cuda.is_available()) else "cpu"
        self._prepare_local_model_files(model_dir)
        self.tts = TTS(model_name=model_name, progress_bar=False, gpu=(self.device == "cuda"))
        synthesizer = getattr(self.tts, "synthesizer", None)
        self.sample_rate = int(getattr(synthesizer, "output_sample_rate", 24000))
        self.speakers = list(getattr(self.tts, "speakers", []) or [])
        self.languages = list(getattr(self.tts, "languages", []) or [])

    @staticmethod
    def _prepare_local_model_files(model_dir: str) -> None:
        if not model_dir:
            return
        src = Path(model_dir)
        if not src.exists():
            return
        target = Path(os.environ["TTS_HOME"]) / "tts_models--multilingual--multi-dataset--xtts_v2"
        target.mkdir(parents=True, exist_ok=True)
        for name in ("model.pth", "config.json", "vocab.json", "hash.md5", "speakers_xtts.pth"):
            source_file = src / name
            target_file = target / name
            if source_file.exists() and not target_file.exists():
                shutil.copy2(source_file, target_file)

    def synthesize(
        self,
        text: str,
        language: str,
        speaker_wav: str | None = None,
        speaker: str | None = None,
    ) -> np.ndarray:
        kwargs = {"text": text}
        if language:
            kwargs["language"] = language

        if speaker_wav:
            kwargs["speaker_wav"] = speaker_wav
        elif speaker:
            kwargs["speaker"] = speaker
        elif self.speakers:
            kwargs["speaker"] = self.speakers[0]
        else:
            raise RuntimeError(
                "Для XTTS-v2 нужен reference голос. Передайте speaker_wav или задайте voice_generator.reference_wav в config.json."
            )

        wav = self.tts.tts(**kwargs)
        audio = np.asarray(wav, dtype=np.float32)
        audio = np.clip(audio, -1.0, 1.0)
        return (audio * 32767.0).astype(np.int16)


def get_voice() -> XttsRuntime:
    global _voice
    if _voice is not None:
        return _voice
    with _voice_lock:
        if _voice is None:
            _voice = XttsRuntime(
                model_name=VOICE["model_name"],
                model_dir=VOICE["model_dir"],
                use_cuda=VOICE["use_cuda"],
            )
    return _voice


def synthesize_wav_bytes(
    text: str,
    language: str,
    speaker_wav: str | None,
    speaker: str | None,
) -> io.BytesIO:
    voice = get_voice()
    with _synth_lock:
        audio = voice.synthesize(
            text=text,
            language=language,
            speaker_wav=speaker_wav,
            speaker=speaker,
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
    for token in ("**", "__", "*", "`", "#", "---"):
        cleaned = cleaned.replace(token, " ")
    cleaned = cleaned.replace("•", " ")
    cleaned = cleaned.replace("- ", " ")
    cleaned = cleaned.replace("-", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


@app.get("/health")
def health():
    ok = True
    error = ""
    runtime = None
    try:
        runtime = get_voice()
    except Exception as exc:
        ok = False
        error = str(exc)

    return jsonify(
        {
            "status": "ok" if ok else "error",
            "engine": "coqui_xtts_v2",
            "model_name": VOICE.get("model_name"),
            "model_dir": VOICE.get("model_dir"),
            "device": (runtime.device if runtime else ("cuda" if VOICE.get("use_cuda") else "cpu")),
            "language": VOICE.get("language"),
            "reference_wav": VOICE.get("reference_wav"),
            "speakers_count": (len(runtime.speakers) if runtime else 0),
            "error": error,
        }
    )


@app.post("/speak")
def speak():
    data = request.get_json(silent=True) or {}
    text = normalize_tts_text((data.get("text") or "").strip())
    if not text:
        return jsonify({"error": "text is required"}), 400

    # Keep backward compatibility with existing STT payload.
    language = str(data.get("language") or VOICE["language"]).strip() or "ru"
    speaker_wav = str(data.get("speaker_wav") or VOICE["reference_wav"] or "").strip()
    speaker = str(data.get("speaker") or VOICE.get("speaker") or "").strip()

    if speaker_wav and not Path(speaker_wav).exists():
        return jsonify({"error": f"speaker_wav not found: {speaker_wav}"}), 400

    try:
        wav_buf = synthesize_wav_bytes(
            text=text,
            language=language,
            speaker_wav=speaker_wav or None,
            speaker=speaker or None,
        )
        return send_file(wav_buf, mimetype="audio/wav", as_attachment=False, download_name="speech.wav")
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    host = VOICE["host"]
    port = VOICE["port"]
    print(
        f"VOICE_GENERATOR on http://{host}:{port} | engine=coqui_xtts_v2 | model={VOICE['model_name']}",
        flush=True,
    )
    app.run(host=host, port=port, debug=False, use_reloader=False)
