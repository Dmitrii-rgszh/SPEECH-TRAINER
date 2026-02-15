# Talking Avatar (LivePortrait → Wav2Lip)

Минимальный production‑pipeline talking‑avatar для речевого тренажёра.

Pipeline (строго):

```
image → LivePortrait (idle + head motion + blink) → base.mp4
base.mp4 + audio → Wav2Lip (mouth only) → lipsynced.mp4
ffmpeg encode → final.mp4
```

## Требования

- Windows 10/11
- CUDA 11.x/12.x, RTX 3060 Ti (8GB)
- Python 3.10
- FFmpeg + FFprobe в PATH (или указать `FFMPEG_PATH`/`FFPROBE_PATH`)

## Установка

```bash
cd E:\SPEECH TRAINER\TALKING_AVATAR
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Модели

### LivePortrait (официальный репозиторий)

1) Клонируй официальный репозиторий в:

```
models/liveportrait
```

2) Скачай веса согласно инструкциям LivePortrait.

### Wav2Lip

1) Клонируй официальный репозиторий в:

```
models/wav2lip
```

2) Скачай веса `wav2lip_gan.pth` и положи в:

```
models/wav2lip/checkpoints/wav2lip_gan.pth
```

## Запуск

```bash
.\.venv\Scripts\python.exe app.py
```

API поднимется на `http://127.0.0.1:7010`.

## API

### POST /generate

multipart/form-data:

- `image`: jpg/png
- `audio`: wav/mp3

Ответ: mp4 файл.

### Пример curl

```bash
curl -X POST "http://127.0.0.1:7010/generate" ^
  -F "image=@E:/path/to/face.png" ^
  -F "audio=@E:/path/to/audio.wav" ^
  --output result.mp4
```

### Preview режим (до Wav2Lip)

```bash
curl -X POST "http://127.0.0.1:7010/generate?preview=true" ^
  -F "image=@E:/path/to/face.png" ^
  -F "audio=@E:/path/to/audio.wav" ^
  --output base.mp4
```

## Переменные окружения

Используй при необходимости:

- `FFMPEG_PATH`, `FFPROBE_PATH`
- `LIVEPORTRAIT_REPO`, `LIVEPORTRAIT_PYTHON`
- `LIVEPORTRAIT_DRIVING` — шаблон driving video (по умолчанию `assets/examples/driving/d0.mp4`)
- `WAV2LIP_REPO`, `WAV2LIP_PYTHON`, `WAV2LIP_CHECKPOINT`
- `LIVEPORTRAIT_CMD` — свой шаблон команды (плейсхолдеры: `{image} {duration} {output} {fps}`)
- `LIVEPORTRAIT_ARGS` — дополнительные аргументы к LivePortrait
- `WAV2LIP_ARGS` — дополнительные аргументы к Wav2Lip
- `KEEP_TEMP=1` — не удалять временные файлы

## CUDA

Модели запускаются по очереди, batch=1. Для ускорения включай fp16 в настройках LivePortrait/Wav2Lip (если поддерживается репозиториями).

## Notes

- Параметры `fps=25`, `crf=18`, `yuv420p` заданы в `pipeline/ffmpeg_encode.py`.
- Ресайз не применяется.
