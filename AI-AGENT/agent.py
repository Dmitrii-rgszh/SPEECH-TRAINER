from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from ollama_client import OllamaClient
from prompts import summarize_prompt, system_prompt


@dataclass
class AgentConfig:
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b-instruct"
    temperature: float = 0.4
    num_ctx: int = 8192
    product: str = ""
    tone: str = "дружелюбный, деловой"
    target: str = "прокачка продаж по телефону"


@dataclass
class SalesTrainerAgent:
    cfg: AgentConfig
    client: OllamaClient = field(init=False)
    dialog_summary: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.client = OllamaClient(self.cfg.base_url)
        self.messages = [
            {
                "role": "system",
                "content": system_prompt(
                    product=self.cfg.product,
                    tone=self.cfg.tone,
                    target=self.cfg.target,
                ),
            }
        ]

    def _with_summary(self) -> List[Dict[str, str]]:
        if not self.dialog_summary.strip():
            return list(self.messages)

        injected = list(self.messages)
        injected.insert(
            1,
            {
                "role": "system",
                "content": f"Сводка контекста (актуализируй ответы с учётом этого):\n{self.dialog_summary}",
            },
        )
        return injected

    def reply(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        assistant_text = self.client.chat(
            self.cfg.model,
            self._with_summary(),
            temperature=self.cfg.temperature,
            num_ctx=self.cfg.num_ctx,
        )
        self.messages.append({"role": "assistant", "content": assistant_text})
        return assistant_text

    def update_summary(self, last_n_turns: int = 6) -> str:
        recent = self.messages[-(last_n_turns * 2) :]
        recent_dialog = "\n".join(
            [f"{m['role']}: {m['content']}" for m in recent if m.get("role") != "system"]
        )
        prompt = summarize_prompt(self.dialog_summary, recent_dialog)

        summary = self.client.chat(
            self.cfg.model,
            [
                {"role": "system", "content": "Ты — помощник, который сжимает контекст диалога."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            num_ctx=self.cfg.num_ctx,
        )
        self.dialog_summary = summary.strip()
        return self.dialog_summary


def load_config(path: str | Path) -> AgentConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ollama = data.get("ollama", {})
    trainer = data.get("trainer", {})

    return AgentConfig(
        base_url=str(ollama.get("base_url", "http://localhost:11434")),
        model=str(ollama.get("model", "qwen2.5:7b-instruct")),
        temperature=float(ollama.get("temperature", 0.4)),
        num_ctx=int(ollama.get("num_ctx", 8192)),
        product=str(trainer.get("product", "")),
        tone=str(trainer.get("tone", "дружелюбный, деловой")),
        target=str(trainer.get("target", "прокачка продаж по телефону")),
    )
