from __future__ import annotations

import argparse

from agent import SalesTrainerAgent, load_config


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Sales Trainer (Ollama)")
    ap.add_argument(
        "--config",
        default="config.example.json",
        help="Path to config JSON (default: config.example.json)",
    )
    ap.add_argument(
        "--summarize-every",
        type=int,
        default=4,
        help="Update summary every N user turns (default: 4)",
    )
    args = ap.parse_args()

    cfg = load_config(args.config)
    agent = SalesTrainerAgent(cfg)

    if not agent.client.health():
        raise SystemExit(
            "Ollama не отвечает на http://localhost:11434. Запусти Ollama и попробуй снова."
        )

    print(f"Model: {cfg.model}")
    print("Команды: /sum (показать сводку), /quit")

    turn = 0
    while True:
        user_text = input("\nВы: ").strip()
        if not user_text:
            continue
        if user_text in {"/quit", "/exit"}:
            break
        if user_text == "/sum":
            print("\n--- Сводка ---\n" + (agent.dialog_summary or "(пусто)"))
            continue

        turn += 1
        answer = agent.reply(user_text)
        print("\nАгент: " + answer)

        if args.summarize_every > 0 and turn % args.summarize_every == 0:
            agent.update_summary()


if __name__ == "__main__":
    main()
