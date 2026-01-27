# STT MVP (RU)

Минимальный MVP распознавания русской речи с открытой моделью Whisper.

## Установка

1. Создайте виртуальное окружение.
2. Установите зависимости:
   - `pip install -r requirements.txt`

## Запуск

- `python app.py`
- Откройте http://127.0.0.1:5000

## Скачивание модели заранее

Модель и кэш Hugging Face теперь сохраняются в папке проекта:

- `STT/.cache/hf`
- `STT/.cache/whisper`

Чтобы скачать модель до запуска сервера:

- `python -c "from faster_whisper import WhisperModel; WhisperModel('medium', device='cuda', compute_type='float16', download_root=r'.\\.cache\\whisper')"`

## GPU (обязательно)

1. Установите CUDA‑версию PyTorch под вашу видеокарту и версию CUDA.
2. Запускайте приложение с переменными окружения:

- `WHISPER_DEVICE=cuda`
- `WHISPER_COMPUTE_TYPE=float16`

Пример (PowerShell):

- `setx WHISPER_DEVICE cuda`
- `setx WHISPER_COMPUTE_TYPE float16`
- `python app.py`

## Параметры

- `WHISPER_MODEL` — размер модели (`tiny`, `base`, `small`, `medium`, `large-v3`). По умолчанию `medium`.
- `WHISPER_DEVICE` — `cpu` или `cuda`.
- `WHISPER_COMPUTE_TYPE` — `int8`, `int8_float16`, `float16`, `float32`.

Пример:

- `set WHISPER_MODEL=small`
- `python app.py`

## LLM (чат-агент)

STT UI поддерживает диалог с LLM: финальная транскрипция автоматически отправляется в `/chat`, ответ добавляется в чат.
В модульной архитектуре `/chat` в STT является прокси в отдельный сервис **AI-AGENT**.

### Провайдеры

Выбираются переменной окружения (в AI-AGENT):

- `LLM_PROVIDER=ollama` (по умолчанию)
- `LLM_PROVIDER=openai_compat` (любой сервер с OpenAI-совместимым `/v1/chat/completions`)

Общие настройки (перекрывают provider-specific):

- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY` (обычно нужно только для `openai_compat`)
- `LLM_TEMPERATURE`
- `LLM_NUM_CTX`

### Ollama (локально)

По умолчанию:

- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=qwen2.5:7b-instruct`

### OpenAI-compatible server (Ubuntu)

Пример (если у тебя поднят совместимый сервер на 8000):

- `setx LLM_PROVIDER openai_compat`
- `setx LLM_BASE_URL http://127.0.0.1:8000`
- `setx LLM_MODEL qwen2.5:7b-instruct`

После этого UI будет использовать твой сервер без привязки к Ollama.

## One-click запуск (Windows)

В корне проекта есть скрипты:

- [start_all.cmd](../start_all.cmd) — проверяет локальную Ollama, подтягивает модель (если нет), запускает AI-AGENT, затем STT.
- [stop_all.ps1](../stop_all.ps1) — останавливает Docker-сервисы.
