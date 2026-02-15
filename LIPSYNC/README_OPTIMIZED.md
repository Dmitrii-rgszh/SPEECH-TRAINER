# Оптимизированный LIPSYNC Pipeline

## Реализованные требования ТЗ

### 5.1 Precompute лица ✅
- Face detection выполняется **1 раз** при первом запросе
- Сохраняются:
  - `precompute/first_coeff.mat` - 3DMM коэффициенты
  - `precompute/avatar_cropped.png` - обрезанный аватар
  - `precompute/face_meta.json` - метаданные
- При последующих запросах используется кэш

### 5.2 Чанкинг аудио ✅
- Максимальная длина чанка: 3 секунды
- Реализовано в `optimized_pipeline.py`

### 5.3 FP16/AMP ✅
- Модели конвертируются в half precision
- Используется `torch.cuda.amp.autocast()`
- Экономия VRAM ~40-50%

### 5.4 Face Enhancement ✅
- Enhancer **отключен** по умолчанию
- Не применяется к каждому чанку

### 5.5 Разрешение и FPS ✅
- Resolution: **512×512** (не 1024!)
- FPS: **25**

### 5.6 Видео-кодирование ✅
- Кодек: H.264 (libx264)
- Preset: **ultrafast**
- CRF: 26
- movflags: +faststart

### 5.7 Управление CUDA-контекстом ✅
- Модели загружаются **1 раз** при старте
- Warm-up inference выполняется
- CUDA контекст не пересоздаётся

### 5.8 Motion-параметры ✅
- expression_scale: **0.3** (≤0.3 по ТЗ)
- still_mode: True
- Минимальная мимика

## Запуск оптимизированного сервера

```powershell
cd E:\SPEECH TRAINER\LIPSYNC
& "E:\SPEECH TRAINER\LIPSYNC\.venv\Scripts\python.exe" app_optimized.py
```

## API Endpoints

### GET /health
Статус сервиса и пайплайна.

### POST /generate
Генерация видео.
- Body: `multipart/form-data` с полем `audio` (WAV файл)
- Returns: `video/mp4`

### POST /precompute
Принудительный precompute лица для текущего аватара.
- Очищает кэш и выполняет precompute заново

### GET /stats
Статистика пайплайна.

## Ожидаемые улучшения производительности

| Метрика | До | После | Улучшение |
|---------|-----|-------|-----------|
| Первый запрос | ~20 сек | ~12-15 сек | 1.3-1.7× |
| Последующие | ~20 сек | ~6-10 сек | 2-3× |
| VRAM | ~6 GB | ~3-4 GB | 1.5× |

## Структура файлов

```
LIPSYNC/
├── app.py              # Старый сервер
├── app_optimized.py    # Новый оптимизированный сервер
├── optimized_pipeline.py  # Модульный pipeline
└── README_OPTIMIZED.md # Эта документация

E:/musetalk_tmp/
├── precompute/         # Кэш face precompute
│   ├── first_coeff.mat
│   ├── avatar_cropped.png
│   └── face_meta.json
└── h264_*.mp4          # Выходные видео
```

## Тестирование

```powershell
# Проверка health
Invoke-RestMethod -Uri "http://127.0.0.1:7002/health"

# Принудительный precompute
Invoke-RestMethod -Uri "http://127.0.0.1:7002/precompute" -Method Post

# Генерация видео
$resp = Invoke-WebRequest -Uri "http://127.0.0.1:7002/generate" -Method Post -Form @{
    audio = Get-Item "E:\musetalk_tmp\test_audio.wav"
} -TimeoutSec 120
[IO.File]::WriteAllBytes("E:\musetalk_tmp\test_output.mp4", $resp.Content)
```

## Логика работы

```
1. Первый запрос:
   [Face Precompute] → [Audio2Coeff] → [AnimateFromCoeff] → [H.264 Encode]
   ↓ сохраняем кэш

2. Последующие запросы:
   [Кэш] → [Audio2Coeff] → [AnimateFromCoeff] → [H.264 Encode]
   ↓ пропускаем precompute (экономия ~5-8 сек)
```

## Переключение на оптимизированный сервер

Для переключения на новый сервер, замените команду запуска:

```powershell
# Старый
python app.py

# Новый (оптимизированный)
python app_optimized.py
```

API совместим — клиенты не требуют изменений.
