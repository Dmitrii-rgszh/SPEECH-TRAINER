# VISEMA 2.0 - Production Talking Avatar Pipeline

Профессиональная система генерации разговаривающего аватара на основе нейросетевых моделей.

## 🎯 Возможности

- **LivePortrait**: Генерация натуральной анимации лица (моргание, движение головы)
- **Wav2Lip**: Синхронизация движения рта с аудиодорожкой
- **FFmpeg**: Быстрое и качественное кодирование видео
- **GPU Accelerated**: Оптимизация для NVIDIA RTX 3060 Ti (и выше)
- **Flask API**: REST API для интеграции в приложения

## 📋 Требования

### Система
- Python 3.10+
- CUDA 12.1+ (для GPU ускорения)
- FFmpeg 4.4+
- Минимум 8GB VRAM (для RTX 3060 Ti)

### Python пакеты
Все зависимости указаны в `requirements.txt`

```bash
torch==2.1.0  # с CUDA 12.1
torchvision==0.16.0
liveportrait  # официальный пакет
wav2lip  # lip-sync модель
flask==3.0.0
opencv-python==4.8.0.74
pillow==10.0.0
numpy==1.24.3
scipy==1.11.3
librosa==0.10.0
imageio==2.32.0
imageio-ffmpeg==0.4.9
```

## 🚀 Установка

### 1. Клонируем репозитории моделей

```bash
cd models/

# LivePortrait (KwaiVGI official)
git clone https://github.com/KwaiVGI/LivePortrait.git liveportrait
cd liveportrait
pip install -e .
cd ..

# Wav2Lip
git clone https://github.com/Rudrabha/Wav2Lip.git wav2lip
cd wav2lip
pip install -r requirements.txt
cd ..
```

### 2. Скачиваем веса моделей

#### LivePortrait checkpoints
```bash
cd models/liveportrait
# Скачать из: https://github.com/KwaiVGI/LivePortrait/releases
# Распаковать в checkpoints/
```

Нужны файлы:
- `appearance_feature_extractor.pth`
- `motion_extractor.pth`
- `warping_module.pth`
- `spade_generator.pth`

#### Wav2Lip checkpoint
```bash
cd models/wav2lip
# Скачать из: https://github.com/Rudrabha/Wav2Lip/releases/download/checkpoints/
# Переименовать в checkpoint.pth
```

### 3. Устанавливаем зависимости

```bash
pip install -r requirements.txt
```

### 4. Проверяем конфигурацию

```bash
python -c "from pipeline.utils import log_config; log_config()"
```

Должно вывести:
```
✓ GPU найден: NVIDIA GeForce RTX 3060 Ti (8.0 GB)
✓ FFmpeg найден
```

## 💻 Использование

### Через API

```bash
# Запуск сервера
python app.py

# В другом терминале - генерация видео
curl -X POST http://127.0.0.1:5000/generate \
  -F "image=@face.jpg" \
  -F "audio=@speech.wav"

# Ответ:
{
  "session_id": "a1b2c3d4",
  "status": "processing",
  "download_url": "/download/a1b2c3d4"
}

# Проверить статус
curl http://127.0.0.1:5000/status/a1b2c3d4

# Скачать результат (когда готов)
curl http://127.0.0.1:5000/download/a1b2c3d4 > output.mp4
```

### Через веб-интерфейс

1. Запустите сервер: `python app.py`
2. Откройте: `http://127.0.0.1:5000`
3. Загрузите изображение лица (JPG/PNG) и аудиофайл (WAV/MP3)
4. Нажмите "Generate Video"
5. Дождитесь завершения и скачайте результат

### Программно

```python
from pipeline.liveportrait_runner import LivePortraitRunner
from pipeline.wav2lip_runner import run_wav2lip
from pipeline.ffmpeg_encode import FFmpegEncoder

# 1. Базовая анимация (моргание + движение головы)
lp = LivePortraitRunner(device='cuda')
lp.run('face.jpg', duration_sec=5.0, output='liveportrait.mp4')
lp.cleanup()

# 2. Синхронизация рта с аудио
run_wav2lip('liveportrait.mp4', 'speech.wav', 'with_lipsync.mp4')

# 3. Финальное кодирование
encoder = FFmpegEncoder()
encoder.encode('with_lipsync.mp4', 'final.mp4', audio_path='speech.wav')
```

## 📊 Производительность

На RTX 3060 Ti (8GB VRAM):

| Параметр | Значение |
|----------|----------|
| LivePortrait (5 сек) | ~2 сек |
| Wav2Lip (5 сек) | ~1 сек |
| FFmpeg кодирование | ~0.5 сек |
| **Итого** | **~3.5 сек** |
| Макс видео | 30 сек |

## 🏗️ Архитектура

```
app.py (Flask API)
    ├── /generate (POST) - основной endpoint
    ├── /status/<id> (GET) - статус обработки
    ├── /download/<id> (GET) - скачивание результата
    └── / (GET) - веб-интерфейс

pipeline/
├── liveportrait_runner.py - базовая анимация
├── wav2lip_runner.py - lip-sync
├── ffmpeg_encode.py - кодирование
└── utils.py - конфигурация и логирование
```

### Pipeline этапы

1. **LivePortrait**: Берет одно изображение лица и генерирует видео с:
   - Естественным морганием
   - Микродвижениями головы
   - Дыхательными движениями

2. **Wav2Lip**: Синхронизирует область рта с аудио:
   - Анализирует спектрограмму аудио
   - Генерирует соответствующие движения рта
   - Сохраняет остальную анимацию от LivePortrait

3. **FFmpeg**: Финальное кодирование:
   - Кодек: H.264 (libx264)
   - Битрейт: высокий (CRF 18)
   - Формат: MP4 с встроенной аудиодорожкой

## ⚙️ Конфигурация

### Config класс (pipeline/utils.py)

```python
class Config:
    # Директории
    MODELS_DIR = Path('models')
    TEMP_DIR = Path('temp')
    OUTPUTS_DIR = Path('outputs')
    
    # Модели
    LIVEPORTRAIT_CKPT = MODELS_DIR / 'liveportrait' / 'checkpoints'
    WAV2LIP_CHECKPOINT = MODELS_DIR / 'wav2lip' / 'checkpoint.pth'
    
    # FFmpeg параметры
    FFMPEG_ENCODING = {
        'vcodec': 'libx264',      # видео-кодек
        'pix_fmt': 'yuv420p',     # пиксельный формат
        'profile': 'high',        # профиль
        'level': '4.2',           # level
        'crf': '18',              # качество (0-51, ниже=лучше)
        'r': '25'                 # frame rate (fps)
    }
    
    # GPU
    DEVICE = 'cuda'  # или 'cpu'
    FP16 = True      # полуточность для экономии памяти
```

## 🐛 Troubleshooting

### "CUDA out of memory"

Решение:
```python
# Используйте CPU вместо GPU
Config.DEVICE = 'cpu'

# Или снизьте качество
Config.FFMPEG_ENCODING['crf'] = '24'  # вместо '18'
```

### "FFmpeg not found"

Установите FFmpeg:
- Windows: `choco install ffmpeg` или скачайте с https://ffmpeg.org
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`

### "LivePortrait checkpoints not found"

Скачайте веса из GitHub releases:
```bash
cd models/liveportrait/checkpoints
# Все 4 файла .pth должны быть здесь
```

### "Wav2Lip checkpoint.pth not found"

Скачайте из: https://github.com/Rudrabha/Wav2Lip/releases
```bash
cd models/wav2lip
# checkpoint.pth должен быть здесь
```

## 📝 Логирование

Логи выводятся в console и сохраняются в:
```
outputs/
├── {session_id}.mp4
├── {session_id}.log
└── ...
```

Уровни логирования:
- INFO - основная информация
- WARNING - предупреждения
- ERROR - ошибки (требуют внимания)

## 📚 Документация моделей

- **LivePortrait**: https://github.com/KwaiVGI/LivePortrait
- **Wav2Lip**: https://github.com/Rudrabha/Wav2Lip
- **FFmpeg**: https://ffmpeg.org/documentation.html

## 🤝 Интеграция

### Docker (опционально)

```dockerfile
FROM pytorch/pytorch:2.1.0-cuda12.1-runtime-ubuntu22.04

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "app.py"]
```

Запуск:
```bash
docker build -t visema .
docker run --gpus all -p 5000:5000 visema
```

### Celery (для асинхронной обработки)

```python
from celery import Celery

celery_app = Celery('visema')

@celery_app.task
def generate_video_task(image_path, audio_path):
    # асинхронная обработка
    pass
```

## 📄 Лицензия

MIT License

## 👨‍💻 Автор

Senior Python/ML Engineer

---

**Версия**: 2.0.0  
**Дата**: 2024  
**Статус**: Production Ready
