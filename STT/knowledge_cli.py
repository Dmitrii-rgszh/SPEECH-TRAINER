from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

from knowledge import (
    import_pdf,
    import_pdf_folder,
    load_catalog,
    load_pack,
    save_pack,
)


ROOT_DIR = Path(__file__).resolve().parents[1]


def _safe_print(text: str) -> None:
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + "\n")


def _print_json(payload: dict | list) -> None:
    _safe_print(json.dumps(payload, ensure_ascii=False, indent=2))


def _load_config(base_dir: str) -> dict:
    path = Path(base_dir) / "config.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _llm_config(base_dir: str) -> dict:
    cfg = _load_config(base_dir)
    llm = cfg.get("llm", {}) if isinstance(cfg.get("llm"), dict) else {}
    provider = str(os.getenv("LLM_PROVIDER") or llm.get("provider") or "ollama").strip().lower()
    base_url = str(os.getenv("LLM_BASE_URL") or llm.get("base_url") or "http://localhost:11434")
    model = str(os.getenv("LLM_MODEL") or llm.get("model") or "qwen2.5:7b-instruct")
    api_key = str(os.getenv("LLM_API_KEY") or llm.get("api_key") or "")
    temperature = float(os.getenv("LLM_TEMPERATURE") or llm.get("temperature") or 0.2)
    num_ctx = int(float(os.getenv("LLM_NUM_CTX") or llm.get("num_ctx") or 8192))
    num_predict = int(float(os.getenv("LLM_NUM_PREDICT") or llm.get("num_predict") or 180))
    return {
        "provider": provider,
        "base_url": base_url.rstrip("/"),
        "model": model,
        "api_key": api_key,
        "temperature": temperature,
        "num_ctx": num_ctx,
        "num_predict": num_predict,
    }


def _llm_chat(
    base_dir: str,
    messages: list[dict[str, str]],
    timeout_s: float = 120.0,
    max_tokens: int | None = None,
) -> str:
    llm = _llm_config(base_dir)
    provider = llm["provider"]
    if provider == "openai_compat":
        headers = {"Content-Type": "application/json"}
        if llm["api_key"]:
            headers["Authorization"] = f"Bearer {llm['api_key']}"
        payload = {
            "model": llm["model"],
            "messages": messages,
            "temperature": llm["temperature"],
        }
        if max_tokens and max_tokens > 0:
            payload["max_tokens"] = int(max_tokens)
        urls = [f"{llm['base_url']}/v1/chat/completions", f"{llm['base_url']}/chat/completions"]
        last_error = None
        for url in urls:
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json() or {}
                choices = data.get("choices") or []
                if not choices or not isinstance(choices[0], dict):
                    continue
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                if isinstance(content, str):
                    return content.strip()
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"openai_compat chat failed: {last_error}")

    payload = {
        "model": llm["model"],
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": llm["temperature"],
            "num_ctx": llm["num_ctx"],
            "num_predict": int(max_tokens) if (max_tokens and max_tokens > 0) else llm["num_predict"],
        },
    }
    resp = requests.post(f"{llm['base_url']}/api/chat", json=payload, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json() or {}
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str):
        raise RuntimeError("ollama returned invalid content")
    return content.strip()


def _one_line(text: str, max_len: int = 380) -> str:
    line = " ".join(str(text or "").replace("\n", " ").split())
    if len(line) > max_len:
        return line[: max_len - 3].rstrip() + "..."
    return line


def _parse_json_object(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(raw[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _compact_pack_payload(pack: dict, include_answers: bool = False) -> dict:
    ptype = str(pack.get("type") or "")
    content = pack.get("content") if isinstance(pack.get("content"), dict) else {}
    if ptype == "product":
        faq_items = []
        faq = content.get("faq") if isinstance(content.get("faq"), list) else []
        for item in faq[:12]:
            if not isinstance(item, dict):
                continue
            row = {"question": _one_line(str(item.get("question") or ""), max_len=180)}
            if include_answers:
                row["expected_answer"] = _one_line(
                    str(item.get("expected_answer") or ""),
                    max_len=240,
                )
            faq_items.append(row)
        return {
            "type": "product",
            "name": pack.get("name"),
            "core_value": _one_line(str(content.get("core_value") or ""), max_len=280),
            "key_benefits": [
                _one_line(str(v), max_len=180)
                for v in (content.get("key_benefits") if isinstance(content.get("key_benefits"), list) else [])[:14]
            ],
            "client_fit": [
                _one_line(str(v), max_len=180)
                for v in (content.get("client_fit") if isinstance(content.get("client_fit"), list) else [])[:10]
            ],
            "client_not_fit": [
                _one_line(str(v), max_len=180)
                for v in (
                    content.get("client_not_fit")
                    if isinstance(content.get("client_not_fit"), list)
                    else []
                )[:10]
            ],
            "must_mention_points": [
                _one_line(str(v), max_len=180)
                for v in (
                    content.get("must_mention_points")
                    if isinstance(content.get("must_mention_points"), list)
                    else []
                )[:14]
            ],
            "compliance_red_flags": [
                _one_line(str(v), max_len=180)
                for v in (
                    content.get("compliance_red_flags")
                    if isinstance(content.get("compliance_red_flags"), list)
                    else []
                )[:14]
            ],
            "faq": faq_items,
        }
    return {
        "type": "technology",
        "name": pack.get("name"),
        "stages": [
            _one_line(str(v), max_len=180)
            for v in (content.get("stages") if isinstance(content.get("stages"), list) else [])[:14]
        ],
        "discovery_questions": [
            _one_line(str(v), max_len=180)
            for v in (
                content.get("discovery_questions")
                if isinstance(content.get("discovery_questions"), list)
                else []
            )[:14]
        ],
        "objection_handling_patterns": [
            _one_line(str(v), max_len=180)
            for v in (
                content.get("objection_handling_patterns")
                if isinstance(content.get("objection_handling_patterns"), list)
                else []
            )[:14]
        ],
        "next_step_patterns": [
            _one_line(str(v), max_len=180)
            for v in (
                content.get("next_step_patterns")
                if isinstance(content.get("next_step_patterns"), list)
                else []
            )[:14]
        ],
        "recommended_phrases": [
            _one_line(str(v), max_len=180)
            for v in (
                content.get("recommended_phrases")
                if isinstance(content.get("recommended_phrases"), list)
                else []
            )[:14]
        ],
    }


def _normalize_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "y", "да", "истина"}


def _sanitize_for_prompt(value: str, max_len: int = 180) -> str:
    text = _one_line(str(value or ""), max_len=max_len)
    text = "".join(ch for ch in text if ch.isprintable())
    allowed_extra = set(".,:;!?%()[]{}\"'«»+-/№")
    cleaned = "".join(ch if (ch.isalnum() or ch.isspace() or ch in allowed_extra) else " " for ch in text)
    return " ".join(cleaned.split())


def _iter_packs(base_dir: str):
    catalog = load_catalog(base_dir)
    items = catalog.get("items") if isinstance(catalog.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        pack_id = str(item.get("pack_id") or "")
        if not pack_id:
            continue
        pack = load_pack(base_dir, pack_id)
        if not pack:
            continue
        yield pack


def _quality_report(pack: dict) -> dict:
    ptype = str(pack.get("type") or "")
    content = pack.get("content") if isinstance(pack.get("content"), dict) else {}
    score = 100
    issues: list[str] = []

    if ptype == "product":
        if len(str(content.get("core_value") or "").strip()) < 20:
            score -= 12
            issues.append("Слабое/пустое core_value")
        if len(content.get("key_benefits") or []) < 5:
            score -= 18
            issues.append("Мало ключевых преимуществ (<5)")
        if len(content.get("must_mention_points") or []) < 4:
            score -= 14
            issues.append("Мало обязательных акцентов (<4)")
        faq = content.get("faq") if isinstance(content.get("faq"), list) else []
        if len(faq) < 5:
            score -= 14
            issues.append("Мало FAQ вопросов (<5)")
        else:
            unanswered = 0
            for item in faq:
                if not isinstance(item, dict):
                    unanswered += 1
                    continue
                if len(str(item.get("expected_answer") or "").strip()) < 10:
                    unanswered += 1
            if unanswered > 0:
                score -= min(20, unanswered * 2)
                issues.append(f"FAQ без нормальных expected_answer: {unanswered}")
        if len(content.get("compliance_red_flags") or []) < 3:
            score -= 10
            issues.append("Мало compliance-ограничений (<3)")
    elif ptype == "technology":
        if len(content.get("stages") or []) < 4:
            score -= 20
            issues.append("Мало этапов технологии (<4)")
        if len(content.get("discovery_questions") or []) < 6:
            score -= 15
            issues.append("Мало диагностических вопросов (<6)")
        if len(content.get("objection_handling_patterns") or []) < 4:
            score -= 12
            issues.append("Мало паттернов работы с возражениями (<4)")
        if len(content.get("next_step_patterns") or []) < 3:
            score -= 10
            issues.append("Мало паттернов next step (<3)")
    else:
        score -= 30
        issues.append(f"Неизвестный тип pack.type={ptype}")

    raw_excerpt_len = len(str(content.get("raw_excerpt") or ""))
    if raw_excerpt_len < 1000:
        score -= 8
        issues.append("Слишком короткий raw_excerpt (<1000 символов)")

    score = max(0, score)
    return {
        "pack_id": pack.get("pack_id"),
        "name": pack.get("name"),
        "type": ptype,
        "quality_score": score,
        "issues": issues,
    }


def cmd_list(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.base_dir)
    items = catalog.get("items") if isinstance(catalog.get("items"), list) else []
    if args.json:
        _print_json({"items": items})
        return 0
    if not items:
        _safe_print("Каталог пуст.")
        return 0
    for item in items:
        if not isinstance(item, dict):
            continue
        _safe_print(
            f"{item.get('pack_id')} | {item.get('type')} | {item.get('name')} | v{item.get('version')}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    pack = load_pack(args.base_dir, args.pack_id)
    if not pack:
        _safe_print("Пакет не найден.")
        return 2
    _print_json(pack)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    reports = [_quality_report(pack) for pack in _iter_packs(args.base_dir)]
    reports = sorted(reports, key=lambda r: int(r.get("quality_score", 0)))
    if args.json:
        _print_json({"reports": reports})
        return 0
    if not reports:
        _safe_print("Каталог пуст.")
        return 0
    for row in reports:
        _safe_print(
            f"[{row['quality_score']:>3}] {row['pack_id']} ({row['type']}) :: {row['name']}"
        )
        for issue in row["issues"]:
            _safe_print(f"  - {issue}")
    return 0


def cmd_import_pdf(args: argparse.Namespace) -> int:
    item = import_pdf(args.base_dir, args.path)
    _print_json({"ok": True, "item": item})
    return 0


def cmd_import_folder(args: argparse.Namespace) -> int:
    result = import_pdf_folder(args.base_dir, args.path, recursive=not args.no_recursive)
    _print_json({"ok": True, **result})
    return 0


def cmd_export_edit(args: argparse.Namespace) -> int:
    pack = load_pack(args.base_dir, args.pack_id)
    if not pack:
        _safe_print("Пакет не найден.")
        return 2
    out_path = Path(args.output or f"{args.pack_id}.edit.json")
    out_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    _safe_print(f"Экспортировано: {out_path}")
    return 0


def cmd_apply_edit(args: argparse.Namespace) -> int:
    edit_path = Path(args.path)
    if not edit_path.exists():
        _safe_print("Файл правок не найден.")
        return 2
    payload = json.loads(edit_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        _safe_print("Файл правок должен быть JSON-объектом.")
        return 2
    saved = save_pack(args.base_dir, payload)
    _safe_print(f"Сохранено: {saved.get('pack_id')}")
    return 0


def cmd_draft_faq(args: argparse.Namespace) -> int:
    pack = load_pack(args.base_dir, args.pack_id)
    if not pack:
        _safe_print("Пакет не найден.")
        return 2
    if str(pack.get("type")) != "product":
        _safe_print("Команда draft-faq работает только для product паков.")
        return 2

    content = pack.get("content") if isinstance(pack.get("content"), dict) else {}
    faq = content.get("faq") if isinstance(content.get("faq"), list) else []
    if not faq:
        _safe_print("В пакете нет FAQ.")
        return 0

    benefits = content.get("key_benefits") if isinstance(content.get("key_benefits"), list) else []
    must_mention = (
        content.get("must_mention_points")
        if isinstance(content.get("must_mention_points"), list)
        else []
    )
    compliance = (
        content.get("compliance_red_flags")
        if isinstance(content.get("compliance_red_flags"), list)
        else []
    )
    core_value = str(content.get("core_value") or "")

    updates = 0
    skipped = 0
    for idx, item in enumerate(faq):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        current = str(item.get("expected_answer") or "").strip()
        if current and not args.rewrite:
            skipped += 1
            continue

        prompt = (
            "Ты методолог банковских продаж. Сформулируй краткий, корректный и понятный "
            "ответ менеджера на FAQ-вопрос клиента. Ответ 1-3 предложения, без воды, без обещаний "
            "гарантированной доходности.\n\n"
            f"Продукт: {pack.get('name')}\n"
            f"Core value: {core_value}\n"
            f"Ключевые преимущества: {json.dumps(benefits[:8], ensure_ascii=False)}\n"
            f"Что обязательно проговорить: {json.dumps(must_mention[:8], ensure_ascii=False)}\n"
            f"Compliance-ограничения: {json.dumps(compliance[:8], ensure_ascii=False)}\n\n"
            f"FAQ-вопрос: {question}\n\n"
            "Верни только текст ответа менеджера, без markdown."
        )
        try:
            reply = _llm_chat(
                args.base_dir,
                [
                    {
                        "role": "system",
                        "content": "Отвечай строго по-русски и по делу.",
                    },
                    {"role": "user", "content": prompt},
                ],
                timeout_s=float(args.timeout),
            )
        except Exception as exc:
            _safe_print(f"[ERR] FAQ #{idx + 1}: {question} :: {exc}")
            continue

        item["expected_answer"] = _one_line(reply, max_len=420)
        updates += 1
        _safe_print(f"[OK] FAQ #{idx + 1}: {question}")

    content["faq"] = faq
    pack["content"] = content
    saved = save_pack(args.base_dir, pack)
    _safe_print(
        f"Готово. Обновлено FAQ: {updates}, пропущено (уже заполнены): {skipped}. "
        f"Сохранен pack: {saved.get('pack_id')}"
    )
    return 0


def cmd_draft_core_value(args: argparse.Namespace) -> int:
    pack = load_pack(args.base_dir, args.pack_id)
    if not pack:
        _safe_print("Пакет не найден.")
        return 2
    if str(pack.get("type")) != "product":
        _safe_print("Команда draft-core-value работает только для product паков.")
        return 2

    content = pack.get("content") if isinstance(pack.get("content"), dict) else {}
    benefits = content.get("key_benefits") if isinstance(content.get("key_benefits"), list) else []
    fit = content.get("client_fit") if isinstance(content.get("client_fit"), list) else []
    must = content.get("must_mention_points") if isinstance(content.get("must_mention_points"), list) else []
    compliance = (
        content.get("compliance_red_flags")
        if isinstance(content.get("compliance_red_flags"), list)
        else []
    )

    prompt = (
        "Сформируй 3 варианта поля core_value для карточки банковского продукта.\n"
        "Требования: 1-2 предложения, простой язык, без обещаний гарантированной доходности, "
        "акцент на ценности для клиента.\n\n"
        f"Название продукта: {pack.get('name')}\n"
        f"Ключевые преимущества: {json.dumps(benefits[:10], ensure_ascii=False)}\n"
        f"Кому подходит: {json.dumps(fit[:8], ensure_ascii=False)}\n"
        f"Обязательные акценты: {json.dumps(must[:8], ensure_ascii=False)}\n"
        f"Compliance-ограничения: {json.dumps(compliance[:8], ensure_ascii=False)}\n\n"
        "Верни строго JSON формата:\n"
        '{"variants":["...","...","..."]}'
    )

    try:
        reply = _llm_chat(
            args.base_dir,
            [
                {"role": "system", "content": "Отвечай строго валидным JSON."},
                {"role": "user", "content": prompt},
            ],
            timeout_s=float(args.timeout),
        )
    except Exception as exc:
        _safe_print(f"Ошибка LLM: {exc}")
        return 2

    parsed = _parse_json_object(reply)
    variants: list[str] = []
    if parsed and isinstance(parsed.get("variants"), list):
        for item in parsed["variants"]:
            text = _one_line(str(item or ""), max_len=320)
            if text:
                variants.append(text)
    if not variants:
        lines = [ln.strip(" -\t") for ln in str(reply).splitlines() if ln.strip()]
        variants = [_one_line(v, max_len=320) for v in lines[:3]]
    variants = [v for v in variants if v]
    if not variants:
        _safe_print("Не удалось получить варианты core_value.")
        return 2

    _safe_print("Варианты core_value:")
    for idx, v in enumerate(variants[:3], 1):
        _safe_print(f"{idx}. {v}")

    if args.apply and variants:
        content["core_value"] = variants[0]
        pack["content"] = content
        save_pack(args.base_dir, pack)
        _safe_print("Применено: core_value обновлен первым вариантом.")
    else:
        _safe_print("Подсказка: добавь --apply, чтобы сразу записать вариант #1 в pack.")
    return 0


def cmd_view_understanding(args: argparse.Namespace) -> int:
    pack = load_pack(args.base_dir, args.pack_id)
    if not pack:
        _safe_print("Пакет не найден.")
        return 2
    ptype = str(pack.get("type") or "")
    content = pack.get("content") if isinstance(pack.get("content"), dict) else {}

    if args.mode == "raw":
        payload = _compact_pack_payload(pack, include_answers=False)
        _print_json(payload)
        return 0

    # LLM mode: show how model "understands" pack and where ambiguity remains.
    compact = _compact_pack_payload(pack, include_answers=False)

    prompt = (
        "Проанализируй knowledge pack и покажи, как ты его понимаешь.\n"
        "Верни строго JSON:\n"
        '{'
        '"summary":"...",'
        '"key_parameters":["..."],'
        '"risks_or_ambiguities":["..."],'
        '"likely_misinterpretations":["..."]'
        '}\n\n'
        f"Тип: {ptype}\n"
        f"Название: {pack.get('name')}\n"
        f"Контент: {json.dumps(compact, ensure_ascii=False)}"
    )
    try:
        reply = _llm_chat(
            args.base_dir,
            [
                {
                    "role": "system",
                    "content": "Отвечай строго валидным JSON без markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            timeout_s=float(args.timeout),
        )
    except Exception as exc:
        _safe_print(f"Ошибка LLM: {exc}")
        return 2

    parsed = _parse_json_object(reply)
    if not parsed:
        _safe_print("LLM не вернула валидный JSON, raw ответ:")
        _safe_print(reply[:4000])
        return 2
    _print_json(parsed)
    return 0


def _strict_check_pack(base_dir: str, pack: dict, count: int, timeout: float) -> dict:
    ptype = str(pack.get("type") or "")
    content = pack.get("content") if isinstance(pack.get("content"), dict) else {}
    if ptype == "product":
        faq = content.get("faq") if isinstance(content.get("faq"), list) else []
        compact = {
            "type": "product",
            "name": _sanitize_for_prompt(pack.get("name"), max_len=120),
            "core_value": _sanitize_for_prompt(content.get("core_value"), max_len=180),
            "key_benefits": [
                _sanitize_for_prompt(v, max_len=120)
                for v in (content.get("key_benefits") if isinstance(content.get("key_benefits"), list) else [])[:8]
            ],
            "must_mention_points": [
                _sanitize_for_prompt(v, max_len=120)
                for v in (
                    content.get("must_mention_points")
                    if isinstance(content.get("must_mention_points"), list)
                    else []
                )[:8]
            ],
            "compliance_red_flags": [
                _sanitize_for_prompt(v, max_len=120)
                for v in (
                    content.get("compliance_red_flags")
                    if isinstance(content.get("compliance_red_flags"), list)
                    else []
                )[:8]
            ],
            "faq_questions": [
                _sanitize_for_prompt((x or {}).get("question"), max_len=120)
                for x in faq[:8]
                if isinstance(x, dict)
            ],
        }
    else:
        compact = {
            "type": "technology",
            "name": _sanitize_for_prompt(pack.get("name"), max_len=120),
            "stages": [
                _sanitize_for_prompt(v, max_len=120)
                for v in (content.get("stages") if isinstance(content.get("stages"), list) else [])[:8]
            ],
            "discovery_questions": [
                _sanitize_for_prompt(v, max_len=120)
                for v in (
                    content.get("discovery_questions")
                    if isinstance(content.get("discovery_questions"), list)
                    else []
                )[:8]
            ],
            "objection_handling_patterns": [
                _sanitize_for_prompt(v, max_len=120)
                for v in (
                    content.get("objection_handling_patterns")
                    if isinstance(content.get("objection_handling_patterns"), list)
                    else []
                )[:8]
            ],
            "next_step_patterns": [
                _sanitize_for_prompt(v, max_len=120)
                for v in (
                    content.get("next_step_patterns")
                    if isinstance(content.get("next_step_patterns"), list)
                    else []
                )[:8]
            ],
        }
    count = max(6, min(40, int(count)))

    # Build deterministic assertions from structured fields (fast, stable),
    # then ask model to classify each statement in short single-turn calls.
    assertions: list[dict] = []
    if ptype == "product":
        kb = compact.get("key_benefits") if isinstance(compact.get("key_benefits"), list) else []
        mm = (
            compact.get("must_mention_points")
            if isinstance(compact.get("must_mention_points"), list)
            else []
        )
        cr = (
            compact.get("compliance_red_flags")
            if isinstance(compact.get("compliance_red_flags"), list)
            else []
        )
        fq = compact.get("faq_questions") if isinstance(compact.get("faq_questions"), list) else []
        if compact.get("core_value"):
            assertions.append(
                {
                    "statement": "В паке продукта заполнено core_value.",
                    "truth": True,
                    "why": "Поле core_value присутствует.",
                }
            )
        assertions.append(
            {
                "statement": "В паке продукта отсутствуют ключевые преимущества.",
                "truth": len(kb) == 0,
                "why": f"Количество key_benefits: {len(kb)}.",
            }
        )
        assertions.append(
            {
                "statement": "В паке продукта есть FAQ-вопросы для проверки знаний менеджера.",
                "truth": len(fq) > 0,
                "why": f"Количество FAQ: {len(fq)}.",
            }
        )
        assertions.append(
            {
                "statement": "В паке продукта нет compliance-ограничений.",
                "truth": len(cr) == 0,
                "why": f"Количество compliance_red_flags: {len(cr)}.",
            }
        )
        for b in kb[:6]:
            assertions.append(
                {
                    "statement": f"В преимуществах продукта явно встречается тезис: «{_sanitize_for_prompt(b, 90)}».",
                    "truth": True,
                    "why": "Это извлечено в key_benefits.",
                }
            )
        for b in kb[:4]:
            assertions.append(
                {
                    "statement": f"В паке нет тезиса про «{_sanitize_for_prompt(b, 90)}».",
                    "truth": False,
                    "why": "Тезис есть в key_benefits.",
                }
            )
        for m in mm[:4]:
            assertions.append(
                {
                    "statement": f"К обязательным акцентам отнесено: «{_sanitize_for_prompt(m, 90)}».",
                    "truth": True,
                    "why": "Пункт есть в must_mention_points.",
                }
            )
        for f in fq[:3]:
            assertions.append(
                {
                    "statement": f"FAQ содержит вопрос: «{_sanitize_for_prompt(f, 100)}».",
                    "truth": True,
                    "why": "Вопрос присутствует в faq_questions.",
                }
            )
        assertions.append(
            {
                "statement": "Пак продукта относится к типу technology.",
                "truth": False,
                "why": "Тип этого пака: product.",
            }
        )
    else:
        stages = compact.get("stages") if isinstance(compact.get("stages"), list) else []
        dq = (
            compact.get("discovery_questions")
            if isinstance(compact.get("discovery_questions"), list)
            else []
        )
        oh = (
            compact.get("objection_handling_patterns")
            if isinstance(compact.get("objection_handling_patterns"), list)
            else []
        )
        ns = (
            compact.get("next_step_patterns")
            if isinstance(compact.get("next_step_patterns"), list)
            else []
        )
        assertions.append(
            {
                "statement": "Пак относится к типу technology.",
                "truth": True,
                "why": "Тип этого пака: technology.",
            }
        )
        assertions.append(
            {
                "statement": "В паке технологии полностью отсутствуют этапы диалога.",
                "truth": len(stages) == 0,
                "why": f"Количество stages: {len(stages)}.",
            }
        )
        assertions.append(
            {
                "statement": "В паке технологии есть диагностические вопросы.",
                "truth": len(dq) > 0,
                "why": f"Количество discovery_questions: {len(dq)}.",
            }
        )
        assertions.append(
            {
                "statement": "В паке технологии нет паттернов работы с возражениями.",
                "truth": len(oh) == 0,
                "why": f"Количество objection_handling_patterns: {len(oh)}.",
            }
        )
        for s in stages[:6]:
            assertions.append(
                {
                    "statement": f"Этап технологии включает формулировку: «{_sanitize_for_prompt(s, 95)}».",
                    "truth": True,
                    "why": "Элемент присутствует в stages.",
                }
            )
        for s in stages[:4]:
            assertions.append(
                {
                    "statement": f"В этапах технологии нет формулировки «{_sanitize_for_prompt(s, 95)}».",
                    "truth": False,
                    "why": "Элемент есть в stages.",
                }
            )
        for q in dq[:4]:
            assertions.append(
                {
                    "statement": f"Диагностический вопрос содержит: «{_sanitize_for_prompt(q, 95)}».",
                    "truth": True,
                    "why": "Элемент есть в discovery_questions.",
                }
            )
        for n in ns[:3]:
            assertions.append(
                {
                    "statement": f"Паттерн следующего шага включает: «{_sanitize_for_prompt(n, 95)}».",
                    "truth": True,
                    "why": "Элемент присутствует в next_step_patterns.",
                }
            )
        assertions.append(
            {
                "statement": "Пак технологии относится к типу product.",
                "truth": False,
                "why": "Тип этого пака: technology.",
            }
        )

    # De-duplicate and trim.
    uniq: list[dict] = []
    seen: set[str] = set()
    for item in assertions:
        key = _one_line(str(item.get("statement") or ""), max_len=260).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    assertions = uniq[:count]
    if len(assertions) < count:
        filler_truth = True
        while len(assertions) < count:
            idx = len(assertions) + 1
            assertions.append(
                {
                    "statement": f"Контрольное утверждение #{idx}: тип пака — {ptype}.",
                    "truth": filler_truth,
                    "why": "Контрольный тест на базовый факт типа пака.",
                }
            )
            filler_truth = not filler_truth

    by_id: dict[int, dict] = {}
    for i, a in enumerate(assertions, 1):
        eval_prompt = (
            "Ответь только JSON без markdown: "
            '{"predicted_truth":true,"confidence":0,"reason":"..."}\n'
            "Оцени утверждение строго по pack_data.\n"
            f"pack_data={json.dumps(compact, ensure_ascii=False)}\n"
            f"statement={json.dumps(a['statement'], ensure_ascii=False)}"
        )
        try:
            answer_raw = _llm_chat(
                base_dir,
                [
                    {"role": "system", "content": "Отвечай только валидным JSON."},
                    {"role": "user", "content": eval_prompt},
                ],
                timeout_s=max(10.0, min(timeout, 25.0)),
                max_tokens=180,
            )
            parsed = _parse_json_object(answer_raw) or {}
            by_id[i] = parsed
        except Exception:
            by_id[i] = {"predicted_truth": False, "confidence": 0, "reason": "timeout_or_error"}

    details: list[dict] = []
    correct = 0
    for i, a in enumerate(assertions, 1):
        ans = by_id.get(i, {})
        predicted = _normalize_bool(ans.get("predicted_truth"))
        is_ok = bool(predicted == a["truth"])
        if is_ok:
            correct += 1
        details.append(
            {
                "id": i,
                "statement": a["statement"],
                "expected_truth": a["truth"],
                "predicted_truth": predicted,
                "is_correct": is_ok,
                "assertion_why": a["why"],
                "model_reason": _one_line(str(ans.get("reason") or ""), max_len=260),
                "confidence": max(0, min(100, int(float(ans.get("confidence") or 0)))),
            }
        )
    total = len(details)
    accuracy = round((correct / total) * 100.0, 2) if total else 0.0
    mismatches = [d for d in details if not d["is_correct"]]

    fixes = {"pack_corrections": [], "prompt_guardrails": [], "qa_tests": []}
    if mismatches:
        fixes["pack_corrections"].append(
            "Укоротить и нормализовать формулировки в списках pack (без спецсимволов из PDF)."
        )
        fixes["pack_corrections"].append(
            "Добавить явные тезисы в core_value и must_mention_points без двусмысленных сокращений."
        )
        fixes["prompt_guardrails"].append(
            "В анализе использовать правило: отвечать только на основе pack_data и помечать недостаток данных."
        )
        fixes["prompt_guardrails"].append(
            "Добавить в system prompt запрет на внешние знания и на догадки по процентам/ставкам."
        )
        for mm in mismatches[:5]:
            fixes["qa_tests"].append(
                f"Перепроверить утверждение #{mm['id']}: {mm['statement']}"
            )

    return {
        "pack_id": pack.get("pack_id"),
        "name": pack.get("name"),
        "type": ptype,
        "assertions_total": total,
        "correct": correct,
        "wrong": total - correct,
        "accuracy_pct": accuracy,
        "details": details,
        "mismatches": mismatches,
        "suggestions": fixes,
    }


def cmd_strict_check(args: argparse.Namespace) -> int:
    packs: list[dict] = []
    if args.pack_id:
        pack = load_pack(args.base_dir, args.pack_id)
        if not pack:
            _safe_print("Пакет не найден.")
            return 2
        packs = [pack]
    else:
        packs = list(_iter_packs(args.base_dir))
    if not packs:
        _safe_print("Каталог пуст.")
        return 0

    reports = []
    for pack in packs:
        try:
            report = _strict_check_pack(
                args.base_dir,
                pack,
                count=int(args.count),
                timeout=float(args.timeout),
            )
            reports.append(report)
            _safe_print(
                f"[OK] strict-check: {report['pack_id']} "
                f"accuracy={report['accuracy_pct']}% ({report['correct']}/{report['assertions_total']})"
            )
        except Exception as exc:
            reports.append(
                {
                    "pack_id": pack.get("pack_id"),
                    "name": pack.get("name"),
                    "type": pack.get("type"),
                    "error": str(exc),
                }
            )
            _safe_print(f"[ERR] strict-check: {pack.get('pack_id')} :: {exc}")

    payload = {"reports": reports}
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _safe_print(f"Сохранено: {out_path}")
    if args.json:
        _print_json(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge_cli",
        description="Утилита контроля качества knowledge packs (без UI).",
    )
    parser.add_argument(
        "--base-dir",
        default=str(ROOT_DIR),
        help="Корень проекта (по умолчанию: текущий repo root).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="Список knowledge packs.")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Показать pack JSON.")
    p_show.add_argument("pack_id")
    p_show.set_defaults(func=cmd_show)

    p_audit = sub.add_parser("audit", help="Quality audit всех паков.")
    p_audit.add_argument("--json", action="store_true")
    p_audit.set_defaults(func=cmd_audit)

    p_imp = sub.add_parser("import-pdf", help="Импорт одного PDF.")
    p_imp.add_argument("path")
    p_imp.set_defaults(func=cmd_import_pdf)

    p_imps = sub.add_parser("import-folder", help="Импорт папки с PDF.")
    p_imps.add_argument("path")
    p_imps.add_argument("--no-recursive", action="store_true")
    p_imps.set_defaults(func=cmd_import_folder)

    p_export = sub.add_parser(
        "export-edit", help="Экспорт pack в .json для ручной правки."
    )
    p_export.add_argument("pack_id")
    p_export.add_argument("--output")
    p_export.set_defaults(func=cmd_export_edit)

    p_apply = sub.add_parser(
        "apply-edit", help="Применить отредактированный JSON обратно в knowledge store."
    )
    p_apply.add_argument("path")
    p_apply.set_defaults(func=cmd_apply_edit)

    p_draft = sub.add_parser(
        "draft-faq",
        help="Заполнить product FAQ.expected_answer черновиками через LLM.",
    )
    p_draft.add_argument("pack_id")
    p_draft.add_argument(
        "--rewrite",
        action="store_true",
        help="Перезаписывать уже заполненные expected_answer.",
    )
    p_draft.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Таймаут одного LLM запроса в секундах.",
    )
    p_draft.set_defaults(func=cmd_draft_faq)

    p_core = sub.add_parser(
        "draft-core-value",
        help="Сгенерировать 3 варианта core_value через LLM (для product pack).",
    )
    p_core.add_argument("pack_id")
    p_core.add_argument(
        "--apply",
        action="store_true",
        help="Сразу применить вариант #1 в pack.",
    )
    p_core.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Таймаут одного LLM запроса в секундах.",
    )
    p_core.set_defaults(func=cmd_draft_core_value)

    p_understanding = sub.add_parser(
        "view-understanding",
        help="Показать, как pack видится: raw структура или LLM-интерпретация.",
    )
    p_understanding.add_argument("pack_id")
    p_understanding.add_argument(
        "--mode",
        choices=["raw", "llm"],
        default="raw",
        help="raw: структурный вид; llm: интерпретация моделью + риски ошибок.",
    )
    p_understanding.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Таймаут LLM в секундах для mode=llm.",
    )
    p_understanding.set_defaults(func=cmd_view_understanding)

    p_strict = sub.add_parser(
        "strict-check",
        help="Строгая проверка понимания pack: 20 true/false + ошибки + рекомендации.",
    )
    p_strict.add_argument("pack_id", nargs="?")
    p_strict.add_argument(
        "--count",
        type=int,
        default=20,
        help="Сколько утверждений сгенерировать (6..40).",
    )
    p_strict.add_argument(
        "--timeout",
        type=float,
        default=150.0,
        help="Таймаут каждого LLM запроса в секундах.",
    )
    p_strict.add_argument(
        "--output",
        help="Путь для сохранения полного JSON-отчета.",
    )
    p_strict.add_argument("--json", action="store_true")
    p_strict.set_defaults(func=cmd_strict_check)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.base_dir = os.path.abspath(args.base_dir)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
