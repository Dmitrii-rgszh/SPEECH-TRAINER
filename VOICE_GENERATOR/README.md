# VOICE_GENERATOR (Piper TTS)

Сервис синтеза речи для озвучивания ответов AI-AGENT через Piper (RHVoice/Piper).

## Что нужно подготовить

1. **Скачай голосовую модель Piper** (`.onnx`) и её конфиг (`.onnx.json`).
2. Положи файлы в удобную папку, например:
   - `E:/SPEECH TRAINER/VOICE_GENERATOR/voices/ru_RU-irina-medium.onnx`
   - `E:/SPEECH TRAINER/VOICE_GENERATOR/voices/ru_RU-irina-medium.onnx.json`
3. **Скачай piper-phonemize (Windows)** и распакуй в `VOICE_GENERATOR/piper-phonemize`:
  - https://github.com/rhasspy/piper-phonemize/releases/download/2023.11.14-4/piper-phonemize_windows_amd64.zip

## Настройка config.json

Добавь секцию `voice_generator`:

```json
{
  "voice_generator": {
    "host": "127.0.0.1",
    "port": 7001,
    "url": "http://127.0.0.1:7001",
    "model_path": "E:/SPEECH TRAINER/VOICE_GENERATOR/voices/ru_RU-irina-medium.onnx",
    "config_path": "E:/SPEECH TRAINER/VOICE_GENERATOR/voices/ru_RU-irina-medium.onnx.json",
    "phonemize_exe": "E:/SPEECH TRAINER/VOICE_GENERATOR/piper-phonemize/piper-phonemize/bin/piper_phonemize_exe.exe",
    "espeak_data": "E:/SPEECH TRAINER/VOICE_GENERATOR/piper-phonemize/piper-phonemize/share/espeak-ng-data",
    "use_cuda": true,
    "speaker_id": 0,
    "length_scale": 1.0,
    "noise_scale": 0.667,
    "noise_w": 0.8
  }
}
```

Можно также задавать переменные окружения:
`PIPER_MODEL_PATH`, `PIPER_CONFIG_PATH`, `PIPER_SPEAKER_ID`, `PIPER_LENGTH_SCALE`, `PIPER_NOISE_SCALE`, `PIPER_NOISE_W`.
Дополнительно для Windows:
`PIPER_PHONEMIZE_EXE`, `PIPER_ESPEAK_DATA`.

## GPU

Для GPU нужен `onnxruntime-gpu` и установленный CUDA runtime (совместимый с версией onnxruntime-gpu).
Включается флагом `use_cuda: true` или переменной `PIPER_USE_CUDA=1`.

## Запуск

Скрипт `start_all.ps1` автоматически установит зависимости и запустит сервис.
Отдельный ручной запуск:

```
python VOICE_GENERATOR/app.py
```

## Проверка

```
GET http://127.0.0.1:7001/health
POST http://127.0.0.1:7001/speak
{ "text": "Привет" }
```
