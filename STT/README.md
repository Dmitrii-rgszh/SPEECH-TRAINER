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
