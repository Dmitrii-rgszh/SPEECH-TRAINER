from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class OllamaClient:
    base_url: str = "http://localhost:11434"

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.4,
        num_ctx: Optional[int] = None,
        stream: bool = False,
        extra_options: Optional[Dict[str, Any]] = None,
        timeout_s: int = 120,
    ) -> str:
        url = f"{self.base_url.rstrip('/')}/api/chat"
        options: Dict[str, Any] = {"temperature": temperature}
        if num_ctx is not None:
            options["num_ctx"] = int(num_ctx)
        if extra_options:
            options.update(extra_options)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": options,
        }

        resp = requests.post(url, json=payload, timeout=timeout_s)
        resp.raise_for_status()

        data = resp.json()
        msg = data.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, str):
            raise RuntimeError(f"Unexpected Ollama response shape: {data}")
        return content

    def health(self, timeout_s: int = 5) -> bool:
        url = f"{self.base_url.rstrip('/')}/api/tags"
        try:
            resp = requests.get(url, timeout=timeout_s)
            return resp.status_code == 200
        except Exception:
            return False
