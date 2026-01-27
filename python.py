from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
APP_PATH = BASE_DIR / "STT" / "app.py"
CONFIG_PATH = BASE_DIR / "config.json"
CONFIG_EXAMPLE_PATH = BASE_DIR / "config.example.json"


def _venv_python_path(base_dir: Path) -> Path:
    if os.name == "nt":
        return base_dir / ".venv" / "Scripts" / "python.exe"
    return base_dir / ".venv" / "bin" / "python"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def env_from_config(cfg: dict) -> dict[str, str]:
    env: dict[str, str] = {}

    whisper = cfg.get("whisper", {}) if isinstance(cfg.get("whisper", {}), dict) else {}
    if whisper.get("model"):
        env["WHISPER_MODEL"] = str(whisper["model"])
    if whisper.get("device"):
        env["WHISPER_DEVICE"] = str(whisper["device"])
    if whisper.get("compute_type"):
        env["WHISPER_COMPUTE_TYPE"] = str(whisper["compute_type"])
    if whisper.get("beam_size") is not None:
        env["WHISPER_BEAM_SIZE"] = str(int(whisper["beam_size"]))

    llm = cfg.get("llm", {}) if isinstance(cfg.get("llm", {}), dict) else {}
    if llm.get("provider"):
        env["LLM_PROVIDER"] = str(llm["provider"])
    if llm.get("base_url"):
        env["LLM_BASE_URL"] = str(llm["base_url"])
    if llm.get("model"):
        env["LLM_MODEL"] = str(llm["model"])
    if llm.get("api_key"):
        env["LLM_API_KEY"] = str(llm["api_key"])
    if llm.get("temperature") is not None:
        env["LLM_TEMPERATURE"] = str(float(llm["temperature"]))
    if llm.get("num_ctx") is not None:
        env["LLM_NUM_CTX"] = str(int(llm["num_ctx"]))
    if llm.get("max_messages") is not None:
        env["CHAT_MAX_MESSAGES"] = str(int(llm["max_messages"]))

    # Backward compatibility: if provider is ollama and LLM_* provided, also fill OLLAMA_*.
    provider = str(llm.get("provider", "")).strip().lower()
    if provider == "ollama":
        if llm.get("base_url"):
            env["OLLAMA_BASE_URL"] = str(llm["base_url"])
        if llm.get("model"):
            env["OLLAMA_MODEL"] = str(llm["model"])
        if llm.get("temperature") is not None:
            env["OLLAMA_TEMPERATURE"] = str(float(llm["temperature"]))
        if llm.get("num_ctx") is not None:
            env["OLLAMA_NUM_CTX"] = str(int(llm["num_ctx"]))

    server = cfg.get("server", {}) if isinstance(cfg.get("server", {}), dict) else {}
    if server.get("host"):
        env["APP_HOST"] = str(server["host"])
    if server.get("port") is not None:
        env["APP_PORT"] = str(int(server["port"]))

    ai_agent = cfg.get("ai_agent", {}) if isinstance(cfg.get("ai_agent", {}), dict) else {}
    if ai_agent.get("host") and ai_agent.get("port") is not None:
        env["AI_AGENT_URL"] = f"http://{ai_agent['host']}:{int(ai_agent['port'])}"

    return env


def maybe_add_cuda_bin(cfg: dict, env: dict[str, str]) -> None:
    cuda = cfg.get("cuda", {}) if isinstance(cfg.get("cuda", {}), dict) else {}
    bin_path = cuda.get("bin_path")
    if not bin_path:
        return
    bin_dir = Path(str(bin_path)).expanduser()
    if not bin_dir.is_absolute():
        bin_dir = (BASE_DIR / bin_dir).resolve()
    if bin_dir.is_dir():
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")


if __name__ == "__main__":
    if not APP_PATH.exists():
        raise SystemExit(f"Не найден файл: {APP_PATH}")

    cfg = load_config()

    venv_py = _venv_python_path(BASE_DIR)
    python_exe = str(venv_py) if venv_py.exists() else sys.executable

    env = os.environ.copy()
    env.update(env_from_config(cfg))
    maybe_add_cuda_bin(cfg, env)

    # Run from STT dir for relative templates/static paths.
    os.chdir(str(BASE_DIR / "STT"))

    if not CONFIG_PATH.exists() and CONFIG_EXAMPLE_PATH.exists():
        print(
            f"[INFO] config.json не найден. Создай его на основе {CONFIG_EXAMPLE_PATH.name} при необходимости.",
            flush=True,
        )

    raise SystemExit(subprocess.call([python_exe, str(APP_PATH)], env=env))
