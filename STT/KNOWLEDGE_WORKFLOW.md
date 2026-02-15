# Knowledge QA Workflow (Без UI)

Этот процесс нужен, чтобы контролировать качество извлечения из PDF и быстро доразмечать знания для анализа тренировки.

## 1) Посмотреть, что загружено
```powershell
python STT/knowledge_cli.py list
```

## 2) Запустить quality audit
```powershell
python STT/knowledge_cli.py audit
```

Смотри `quality_score` и список `issues` по каждому паку.

## 3) Выгрузить пакет в editable JSON
```powershell
python STT/knowledge_cli.py export-edit <pack_id> --output .\tmp_pack.edit.json
```

## 4) Ручная правка JSON (в IDE)
Рекомендуется в первую очередь дополнять:
- product:
  - `content.key_benefits`
  - `content.must_mention_points`
  - `content.faq[].expected_answer`
  - `content.compliance_red_flags`
- technology:
  - `content.stages`
  - `content.discovery_questions`
  - `content.objection_handling_patterns`
  - `content.next_step_patterns`

## 5) Применить правки
```powershell
python STT/knowledge_cli.py apply-edit .\tmp_pack.edit.json
```

## 6) Повторный аудит
```powershell
python STT/knowledge_cli.py audit
```

## Полуавтомат FAQ через LLM
Для product-пака можно автоматически набросать `faq[].expected_answer`:

```powershell
python STT/knowledge_cli.py draft-faq <pack_id>
```

Если нужно перезаписать даже уже заполненные ответы:
```powershell
python STT/knowledge_cli.py draft-faq <pack_id> --rewrite
```

После генерации обязательно:
1. `export-edit` -> открыть JSON в IDE -> точечно поправить.
2. `apply-edit` -> `audit`.

## Полуавтомат core_value (3 варианта)
Сгенерировать 3 варианта `core_value`:
```powershell
python STT/knowledge_cli.py draft-core-value <pack_id>
```

Сразу применить вариант #1:
```powershell
python STT/knowledge_cli.py draft-core-value <pack_id> --apply
```

## Проверка "как ИИ понимает" отдельно продукт и технологию
Структурный view (без LLM):
```powershell
python STT/knowledge_cli.py view-understanding <pack_id> --mode raw
```

Интерпретация LLM (summary + параметры + неоднозначности):
```powershell
python STT/knowledge_cli.py view-understanding <pack_id> --mode llm
```

## Импорт новых PDF
Один файл:
```powershell
python STT/knowledge_cli.py import-pdf "E:\path\doc.pdf"
```

Папка:
```powershell
python STT/knowledge_cli.py import-folder "E:\SPEECH TRAINER\AI-AGENT\KNOWLEDGE"
```

## Где хранятся данные
- Каталог: `data/knowledge/catalog.json`
- Пакеты: `data/knowledge/packs/*.json`

## Где используются в приложении
- Выбор в Wizard: поле `knowledge_refs`
- Анализ встречи: endpoint `POST /analysis/dialog`
