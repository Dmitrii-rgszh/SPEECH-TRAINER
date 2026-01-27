from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
import unicodedata

import requests
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

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


def _env_or(cfg: dict, key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is not None and value != "":
        return value
    return default


def llm_config(cfg: dict) -> dict:
    llm = cfg.get("llm", {}) if isinstance(cfg.get("llm", {}), dict) else {}
    provider = str(_env_or(cfg, "LLM_PROVIDER", str(llm.get("provider", "ollama"))))
    base_url = str(_env_or(cfg, "LLM_BASE_URL", str(llm.get("base_url", "http://localhost:11434"))))
    model = str(_env_or(cfg, "LLM_MODEL", str(llm.get("model", "qwen2.5:7b-instruct"))))
    api_key = str(_env_or(cfg, "LLM_API_KEY", str(llm.get("api_key", ""))))
    temperature = float(_env_or(cfg, "LLM_TEMPERATURE", str(llm.get("temperature", 0.4))))
    num_ctx = int(float(_env_or(cfg, "LLM_NUM_CTX", str(llm.get("num_ctx", 8192)))))
    max_messages = int(float(_env_or(cfg, "CHAT_MAX_MESSAGES", str(llm.get("max_messages", 20)))))

    return {
        "provider": provider.strip().lower(),
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "temperature": temperature,
        "num_ctx": num_ctx,
        "max_messages": max_messages,
    }


def agent_host_port(cfg: dict) -> tuple[str, int]:
    agent = cfg.get("ai_agent", {}) if isinstance(cfg.get("ai_agent", {}), dict) else {}
    host = os.getenv("AGENT_HOST") or str(agent.get("host", "127.0.0.1"))
    port = int(os.getenv("AGENT_PORT") or agent.get("port", 7000))
    return host, port


def agent_system_prompt(cfg: dict) -> str:
    agent = cfg.get("ai_agent", {}) if isinstance(cfg.get("ai_agent", {}), dict) else {}
    prompt = os.getenv("AI_AGENT_SYSTEM_PROMPT") or agent.get(
        "system_prompt",
        "Отвечай строго по-русски. Не добавляй другие языки или иероглифы.",
    )
    return str(prompt).strip()


CONFIG = load_config()
LLM = llm_config(CONFIG)
AGENT_HOST, AGENT_PORT = agent_host_port(CONFIG)
SYSTEM_PROMPT = agent_system_prompt(CONFIG)

chat_lock = threading.Lock()
chat_sessions: dict[str, list[dict[str, str]]] = {}


def ensure_system_prompt(history: list[dict[str, str]]) -> list[dict[str, str]]:
    if not SYSTEM_PROMPT:
        return history
    if history and history[0].get("role") == "system":
        return history
    return [{"role": "system", "content": SYSTEM_PROMPT}] + history


def strip_non_russian(text: str) -> str:
    cleaned_chars: list[str] = []
    for ch in text:
        if ch == "\n" or ch == "\r" or ch == "\t":
            cleaned_chars.append(ch)
            continue
        if ch.isdigit() or ch.isspace():
            cleaned_chars.append(ch)
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("L"):
            name = unicodedata.name(ch, "")
            if "CYRILLIC" in name:
                cleaned_chars.append(ch)
            # else skip non-Cyrillic letters (Latin/CJK/etc.)
            continue
        cleaned_chars.append(ch)
    return "".join(cleaned_chars).strip()


def llm_is_up(timeout_s: float = 1.5) -> bool:
    base_url = LLM["base_url"].rstrip("/")
    try:
        if LLM["provider"] == "openai_compat":
            headers = {}
            if LLM["api_key"]:
                headers["Authorization"] = f"Bearer {LLM['api_key']}"
            resp = requests.get(f"{base_url}/v1/models", headers=headers, timeout=timeout_s)
            if resp.status_code in (200, 401, 403):
                return True
            resp2 = requests.get(f"{base_url}/models", headers=headers, timeout=timeout_s)
            return resp2.status_code in (200, 401, 403)

        resp = requests.get(f"{base_url}/api/tags", timeout=timeout_s)
        return resp.status_code == 200
    except Exception:
        return False


def ollama_model_present(model_name: str, timeout_s: float = 2.5) -> bool:
    if LLM["provider"] != "ollama":
        return False
    base_url = LLM["base_url"].rstrip("/")
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=timeout_s)
        resp.raise_for_status()
        data = resp.json() or {}
        models = data.get("models") or []
        for m in models:
            if isinstance(m, dict) and m.get("name") == model_name:
                return True
        return False
    except Exception:
        return False


def ollama_chat(messages: list[dict[str, str]]) -> str:
    base_url = LLM["base_url"].rstrip("/")
    payload = {
        "model": LLM["model"],
        "messages": messages,
        "stream": False,
        "options": {"temperature": LLM["temperature"], "num_ctx": LLM["num_ctx"]},
    }
    resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"Unexpected Ollama response shape: {data}")
    return content


def openai_compat_chat(messages: list[dict[str, str]]) -> str:
    base_url = LLM["base_url"].rstrip("/")
    headers = {"Content-Type": "application/json"}
    if LLM["api_key"]:
        headers["Authorization"] = f"Bearer {LLM['api_key']}"

    payload = {
        "model": LLM["model"],
        "messages": messages,
        "temperature": LLM["temperature"],
    }

    urls = [f"{base_url}/v1/chat/completions", f"{base_url}/chat/completions"]
    last_exc: Exception | None = None
    for url in urls:
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"Unexpected OpenAI response shape: {data}")
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if not isinstance(content, str):
                raise RuntimeError(f"Unexpected OpenAI response shape: {data}")
            return content
        except Exception as exc:
            last_exc = exc
    raise RuntimeError(f"OpenAI-compatible endpoint not reachable: {last_exc}")


def llm_chat(messages: list[dict[str, str]]) -> str:
    if LLM["provider"] == "openai_compat":
        return openai_compat_chat(messages)
    return ollama_chat(messages)


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "llm": {
                "provider": LLM["provider"],
                "ok": llm_is_up(),
                "base_url": LLM["base_url"],
                "model": LLM["model"],
                "model_present": ollama_model_present(LLM["model"]),
            },
        }
    )


@app.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        return error
    return jsonify({"error": str(error)}), 500


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    reset = bool(data.get("reset", False))
    session_id = (data.get("session_id") or "").strip() or uuid.uuid4().hex

    with chat_lock:
        if reset or session_id not in chat_sessions:
            chat_sessions[session_id] = ensure_system_prompt([])
        history = chat_sessions[session_id]
        history = ensure_system_prompt(history)
        history.append({"role": "user", "content": text})
        # keep system message at the beginning
        if history and history[0].get("role") == "system":
            system_msg = history[0:1]
            tail = history[1:]
            tail = tail[-LLM["max_messages"] :]
            history = system_msg + tail
        else:
            history = history[-LLM["max_messages"] :]
        chat_sessions[session_id] = history

    try:
        reply_text = llm_chat(history)
    except requests.exceptions.ConnectionError:
        provider_hint = (
            "Ollama недоступна. Запусти Ollama на http://localhost:11434"
            if LLM["provider"] == "ollama"
            else "LLM endpoint недоступен (openai_compat). Проверь LLM_BASE_URL и что сервер запущен."
        )
        return (jsonify({"error": provider_hint, "session_id": session_id}), 503)
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if LLM["provider"] == "ollama" and status_code == 404:
            model_name = LLM["model"]
            return (
                jsonify(
                    {
                        "error": (
                            f"Модель '{model_name}' не найдена в Ollama. "
                            f"Если Ollama в Docker: docker exec speech-trainer-ollama ollama pull {model_name}"
                        ),
                        "session_id": session_id,
                    }
                ),
                503,
            )
        raise

    reply_text = strip_non_russian(reply_text)

    with chat_lock:
        history = chat_sessions.get(session_id, [])
        history = ensure_system_prompt(history)
        history.append({"role": "assistant", "content": reply_text})
        if history and history[0].get("role") == "system":
            system_msg = history[0:1]
            tail = history[1:]
            tail = tail[-LLM["max_messages"] :]
            history = system_msg + tail
        else:
            history = history[-LLM["max_messages"] :]
        chat_sessions[session_id] = history

    return jsonify({"reply": reply_text, "session_id": session_id})


if __name__ == "__main__":
    print(
        f"AI-AGENT on http://{AGENT_HOST}:{AGENT_PORT} | provider={LLM['provider']} | base_url={LLM['base_url']} | model={LLM['model']}",
        flush=True,
    )
    app.run(host=AGENT_HOST, port=AGENT_PORT, debug=False, use_reloader=False)
