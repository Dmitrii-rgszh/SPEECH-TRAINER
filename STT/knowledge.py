from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _to_text(value, default: str = "", max_len: int | None = None) -> str:
    text = default if value is None else str(value).strip()
    if max_len is not None and len(text) > max_len:
        return text[:max_len]
    return text


def _to_int(value, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        num = int(value)
    except Exception:
        num = default
    if min_value is not None:
        num = max(min_value, num)
    if max_value is not None:
        num = min(max_value, num)
    return num


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "_", value.strip().lower())
    normalized = normalized.strip("_")
    return normalized or f"pack_{secrets.token_hex(4)}"


def _string_list(value, max_items: int = 64, max_len: int = 220) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _to_text(item, max_len=max_len)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def _knowledge_dirs(base_dir: str) -> tuple[Path, Path]:
    data_root = Path(base_dir) / "data" / "knowledge"
    packs_root = data_root / "packs"
    data_root.mkdir(parents=True, exist_ok=True)
    packs_root.mkdir(parents=True, exist_ok=True)
    return data_root, packs_root


def _catalog_path(base_dir: str) -> Path:
    data_root, _ = _knowledge_dirs(base_dir)
    return data_root / "catalog.json"


def load_catalog(base_dir: str) -> dict:
    path = _catalog_path(base_dir)
    if not path.exists():
        return {"version": 1, "items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"version": 1, "items": []}
        items = payload.get("items")
        if not isinstance(items, list):
            payload["items"] = []
        return payload
    except Exception:
        return {"version": 1, "items": []}


def save_catalog(base_dir: str, catalog: dict) -> None:
    path = _catalog_path(base_dir)
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _extract_pdf_text(pdf_path: Path) -> str:
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed.")
    chunks: list[str] = []
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            chunks.append(page.get_text("text"))
    return "\n".join(chunks)


def _extract_candidate_lines(text: str) -> list[str]:
    raw_lines = [ln.strip() for ln in text.splitlines()]
    lines: list[str] = []
    for line in raw_lines:
        if len(line) < 4:
            continue
        if re.fullmatch(r"[\d\W_]+", line):
            continue
        lines.append(line)
    return lines


def _pick_by_keywords(lines: list[str], keywords: list[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        low = line.lower()
        if not any(k in low for k in keywords):
            continue
        if low in seen:
            continue
        seen.add(low)
        out.append(line)
        if len(out) >= limit:
            break
    return out


def _questions_from_lines(lines: list[str], limit: int = 20) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if "?" not in line:
            continue
        text = line.strip(" -•\t")
        low = text.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def classify_document_type(filename: str) -> str:
    name = filename.lower()
    if "технолог" in name or "продаж" in name:
        return "technology"
    return "product"


def _build_product_pack(filename: str, source_path: str, text: str) -> dict:
    lines = _extract_candidate_lines(text)
    benefits = _pick_by_keywords(
        lines,
        ["преимущ", "выгод", "плюс", "защит", "доход", "сохран", "гарант", "услов"],
        limit=15,
    )
    fit = _pick_by_keywords(lines, ["подходит", "клиент", "сегмент", "для кого"], limit=10)
    not_fit = _pick_by_keywords(
        lines,
        ["не подходит", "не рекомендуется", "огранич", "исключ"],
        limit=10,
    )
    compliance = _pick_by_keywords(
        lines,
        ["нельзя", "запрещ", "не обещ", "гарантирован", "риск", "дисклеймер"],
        limit=12,
    )
    must_mention = _pick_by_keywords(
        lines,
        ["обязательно", "важно", "нужно", "необходимо", "проговор"],
        limit=12,
    )
    questions = _questions_from_lines(lines, limit=14)
    core_value = lines[0] if lines else ""
    return {
        "pack_id": f"product_{_slugify(Path(filename).stem)}",
        "type": "product",
        "name": Path(filename).stem,
        "source_file": source_path,
        "source_filename": filename,
        "version": 1,
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "content": {
            "core_value": core_value,
            "key_benefits": benefits[:12],
            "client_fit": fit[:10],
            "client_not_fit": not_fit[:10],
            "faq": [{"question": q, "expected_answer": ""} for q in questions[:12]],
            "objections": [],
            "compliance_red_flags": compliance[:12],
            "must_mention_points": must_mention[:12],
            "nice_to_mention_points": benefits[12:20],
            "glossary": [],
            "raw_excerpt": "\n".join(lines[:220]),
        },
    }


def _build_technology_pack(filename: str, source_path: str, text: str) -> dict:
    lines = _extract_candidate_lines(text)
    stages = _pick_by_keywords(lines, ["этап", "шаг", "структура", "сценар"], limit=12)
    discovery = _pick_by_keywords(
        lines,
        ["вопрос", "уточн", "потребност", "цель", "срок", "ликвид"],
        limit=14,
    )
    objections = _pick_by_keywords(lines, ["возраж", "сомнен", "ответ"], limit=12)
    next_step = _pick_by_keywords(lines, ["следующ", "договор", "оформ", "подтверж"], limit=10)
    phrases = _pick_by_keywords(lines, ["фраз", "формулиров", "пример"], limit=14)
    questions = _questions_from_lines(lines, limit=14)
    return {
        "pack_id": f"technology_{_slugify(Path(filename).stem)}",
        "type": "technology",
        "name": Path(filename).stem,
        "source_file": source_path,
        "source_filename": filename,
        "version": 1,
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "content": {
            "stages": stages[:12],
            "discovery_questions": questions[:10] or discovery[:10],
            "objection_handling_patterns": objections[:12],
            "next_step_patterns": next_step[:10],
            "recommended_phrases": phrases[:12],
            "raw_excerpt": "\n".join(lines[:220]),
        },
    }


def _normalize_pack(pack: dict) -> dict:
    content = pack.get("content") if isinstance(pack.get("content"), dict) else {}
    type_name = _to_text(pack.get("type"), "product", max_len=24)
    if type_name not in {"product", "technology"}:
        type_name = "product"
    normalized = {
        "pack_id": _to_text(pack.get("pack_id"), f"{type_name}_{secrets.token_hex(6)}", max_len=220),
        "type": type_name,
        "name": _to_text(pack.get("name"), max_len=240),
        "source_file": _to_text(pack.get("source_file"), max_len=1000),
        "source_filename": _to_text(pack.get("source_filename"), max_len=300),
        "version": _to_int(pack.get("version"), 1, min_value=1),
        "created_at": _to_text(pack.get("created_at"), _utc_now_iso(), max_len=40),
        "updated_at": _to_text(pack.get("updated_at"), _utc_now_iso(), max_len=40),
        "content": content if isinstance(content, dict) else {},
    }
    if type_name == "product":
        c = normalized["content"]
        normalized["content"] = {
            "core_value": _to_text(c.get("core_value"), max_len=1200),
            "key_benefits": _string_list(c.get("key_benefits"), max_items=24),
            "client_fit": _string_list(c.get("client_fit"), max_items=24),
            "client_not_fit": _string_list(c.get("client_not_fit"), max_items=24),
            "faq": c.get("faq") if isinstance(c.get("faq"), list) else [],
            "objections": c.get("objections") if isinstance(c.get("objections"), list) else [],
            "compliance_red_flags": _string_list(c.get("compliance_red_flags"), max_items=24),
            "must_mention_points": _string_list(c.get("must_mention_points"), max_items=24),
            "nice_to_mention_points": _string_list(c.get("nice_to_mention_points"), max_items=24),
            "glossary": c.get("glossary") if isinstance(c.get("glossary"), list) else [],
            "raw_excerpt": _to_text(c.get("raw_excerpt"), max_len=40000),
        }
    else:
        c = normalized["content"]
        normalized["content"] = {
            "stages": _string_list(c.get("stages"), max_items=24),
            "discovery_questions": _string_list(c.get("discovery_questions"), max_items=24),
            "objection_handling_patterns": _string_list(
                c.get("objection_handling_patterns"), max_items=24
            ),
            "next_step_patterns": _string_list(c.get("next_step_patterns"), max_items=24),
            "recommended_phrases": _string_list(c.get("recommended_phrases"), max_items=24),
            "raw_excerpt": _to_text(c.get("raw_excerpt"), max_len=40000),
        }
    return normalized


def save_pack(base_dir: str, pack: dict) -> dict:
    _, packs_root = _knowledge_dirs(base_dir)
    normalized = _normalize_pack(pack)
    pack_path = packs_root / f"{normalized['pack_id']}.json"
    pack_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    catalog = load_catalog(base_dir)
    items = catalog.get("items") if isinstance(catalog.get("items"), list) else []
    filtered = [i for i in items if isinstance(i, dict) and i.get("pack_id") != normalized["pack_id"]]
    filtered.append(
        {
            "pack_id": normalized["pack_id"],
            "type": normalized["type"],
            "name": normalized["name"],
            "version": normalized["version"],
            "source_filename": normalized["source_filename"],
            "updated_at": normalized["updated_at"],
            "path": str(pack_path),
        }
    )
    catalog["items"] = sorted(filtered, key=lambda x: str(x.get("updated_at", "")), reverse=True)
    save_catalog(base_dir, catalog)
    return normalized


def load_pack(base_dir: str, pack_id: str) -> dict | None:
    _, packs_root = _knowledge_dirs(base_dir)
    safe_id = _slugify(pack_id)
    direct_path = packs_root / f"{pack_id}.json"
    if direct_path.exists():
        try:
            data = json.loads(direct_path.read_text(encoding="utf-8"))
            return _normalize_pack(data)
        except Exception:
            return None
    fallback_path = packs_root / f"{safe_id}.json"
    if fallback_path.exists():
        try:
            data = json.loads(fallback_path.read_text(encoding="utf-8"))
            return _normalize_pack(data)
        except Exception:
            return None
    return None


def import_pdf(base_dir: str, pdf_path: str) -> dict:
    src = Path(pdf_path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if src.suffix.lower() != ".pdf":
        raise ValueError("Only .pdf files are supported.")
    text = _extract_pdf_text(src)
    doc_type = classify_document_type(src.name)
    if doc_type == "technology":
        pack = _build_technology_pack(src.name, str(src), text)
    else:
        pack = _build_product_pack(src.name, str(src), text)
    return save_pack(base_dir, pack)


def import_pdf_folder(base_dir: str, folder_path: str, recursive: bool = True) -> dict:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    pattern = "**/*.pdf" if recursive else "*.pdf"
    imported: list[dict] = []
    errors: list[dict] = []
    for pdf in sorted(folder.glob(pattern)):
        try:
            imported.append(import_pdf(base_dir, str(pdf)))
        except Exception as exc:
            errors.append({"file": str(pdf), "error": str(exc)})
    return {"imported": imported, "errors": errors}


def bootstrap_from_default_sources(base_dir: str) -> dict:
    catalog = load_catalog(base_dir)
    items = catalog.get("items") if isinstance(catalog.get("items"), list) else []
    if items:
        return {"imported": [], "errors": [], "skipped": "catalog_not_empty"}
    source_dir = Path(base_dir) / "AI-AGENT" / "KNOWLEDGE"
    if not source_dir.exists():
        return {"imported": [], "errors": [], "skipped": "source_missing"}
    return import_pdf_folder(base_dir, str(source_dir), recursive=True)


def analysis_knowledge_context(base_dir: str, scenario: dict) -> dict:
    refs = scenario.get("knowledge_refs") if isinstance(scenario.get("knowledge_refs"), dict) else {}
    product_pack = None
    technology_pack = None
    product_id = _to_text(refs.get("product_pack_id"), max_len=220)
    technology_id = _to_text(refs.get("technology_pack_id"), max_len=220)
    if product_id:
        product_pack = load_pack(base_dir, product_id)
    if technology_id:
        technology_pack = load_pack(base_dir, technology_id)
    return {
        "product_pack_id": product_id,
        "technology_pack_id": technology_id,
        "product_pack": product_pack,
        "technology_pack": technology_pack,
    }

