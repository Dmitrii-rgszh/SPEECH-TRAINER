# VISEMA 2.0 - Quick Start Guide

Пошаговое руководство для запуска talking avatar на вашей системе.

## ⏱️ Займет ~30 минут

## Шаг 1: Проверка системы (5 минут)

### Windows CMD:
```bash
python --version  # Должно быть 3.10+
ffmpeg -version   # Должен быть установлен
nvidia-smi        # Должна быть видна ваша GPU
```

### Linux/macOS:
```bash
python3 --version
ffmpeg -version
nvidia-smi  # только для NVIDIA
```

**Если что-то отсутствует:**
- Python: https://python.org (установите 3.10+)
- FFmpeg: https://ffmpeg.org/download.html
- NVIDIA drivers: https://www.nvidia.com/download/driverDetails.html

## Шаг 2: Клонирование моделей (10 минут)

```bash
cd models/

# LivePortrait
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

## Шаг 3: Скачивание весов моделей (5 минут)

### LivePortrait checkpoints:
```bash
cd models/liveportrait/checkpoints

# Скачайте с GitHub:
# https://github.com/KwaiVGI/LivePortrait/releases/

# Или через wget:
wget https://huggingface.co/KwaiVGI/LivePortrait/resolve/main/appearance_feature_extractor.pth
wget https://huggingface.co/KwaiVGI/LivePortrait/resolve/main/motion_extractor.pth
wget https://huggingface.co/KwaiVGI/LivePortrait/resolve/main/warping_module.pth
wget https://huggingface.co/KwaiVGI/LivePortrait/resolve/main/spade_generator.pth
```

### Wav2Lip checkpoint:
```bash
cd models/wav2lip

# Скачайте с GitHub:
# https://github.com/Rudrabha/Wav2Lip/releases/download/checkpoints/checkpoint.pth

# Или через wget:
wget https://github.com/Rudrabha/Wav2Lip/releases/download/checkpoints/checkpoint.pth
```

## Шаг 4: Установка зависимостей (5 минут)

```bash
pip install -r requirements.txt
```

## Шаг 5: Проверка конфигурации (2 минуты)

```bash
python check_setup.py
```

Должно вывести:
```
✓ OK       Python
✓ OK       PyTorch/CUDA
✓ OK       FFmpeg
✓ OK       Dependencies
✓ OK       Model Paths
✓ OK       LivePortrait
✓ OK       Wav2Lip
✓ OK       Flask App
```

## Шаг 6: Запуск сервера (1 минута)

### Windows:
```bash
run.cmd
```

### Linux/macOS:
```bash
chmod +x run.sh
./run.sh
```

Должно вывести:
```
================================
VISEMA 2.0 - Flask Server
================================

✓ GPU найден: NVIDIA GeForce RTX 3060 Ti (8.0 GB)
✓ FFmpeg найден
✓ Сервер запускается...

Откройте http://127.0.0.1:5000 в браузере
```

## Шаг 7: Тестирование (остальное время)

### Через веб-интерфейс:
1. Откройте http://127.0.0.1:5000 в браузере
2. Загрузите изображение (JPG/PNG) лица
3. Загрузите аудиофайл (WAV/MP3)
4. Нажмите "Generate Video"
5. Дождитесь завершения (~3-5 сек на RTX 3060 Ti)
6. Смотрите результат в браузере!

### Через API (curl):
```bash
curl -X POST http://127.0.0.1:5000/generate \
  -F "image=@face.jpg" \
  -F "audio=@speech.wav"
```

Ответ:
```json
{
  "session_id": "a1b2c3d4",
  "status": "processing",
  "download_url": "/download/a1b2c3d4"
}
```

Проверить статус:
```bash
curl http://127.0.0.1:5000/status/a1b2c3d4
```

Скачать результат:
```bash
curl http://127.0.0.1:5000/download/a1b2c3d4 > output.mp4
```

## 🎬 Примеры использования

### Python код:
```python
from pipeline.liveportrait_runner import LivePortraitRunner
from pipeline.wav2lip_runner import run_wav2lip

# 1. Базовая анимация (5 сек)
lp = LivePortraitRunner(device='cuda')
lp.run('face.jpg', duration_sec=5.0, output='liveportrait.mp4')
lp.cleanup()

# 2. Lip-sync
run_wav2lip('liveportrait.mp4', 'speech.wav', 'final.mp4')
```

### ffmpeg напрямую:
```bash
# Извлечь кадры
ffmpeg -i final.mp4 -f image2 frames/frame_%04d.png

# Добавить аудио
ffmpeg -i liveportrait.mp4 -i speech.wav -c:v copy -c:a aac output.mp4
```

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'torch'"
```bash
pip install torch torchvision torchaudio
```

### "CUDA out of memory"
- Уменьшите разрешение видео
- Используйте CPU (медленнее): просто удалите GPU или установите DEVICE='cpu'
- Снизьте качество: CRF 24 вместо 18

### "FFmpeg not found"
```bash
# Windows
choco install ffmpeg

# Linux
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

### "checkpoint.pth not found"
Проверьте путь:
```bash
ls models/wav2lip/
# Должна быть папка с checkpoint.pth
```

### Видео не генерируется
1. Откройте http://127.0.0.1:5000 и проверьте браузерную консоль (F12)
2. Проверьте консоль сервера (где запустили python app.py)
3. Запустите `python check_setup.py` для диагностики

## 📊 Производительность

На RTX 3060 Ti:
- 5-секундное видео: ~3.5 сек
- 30-секундное видео: ~15 сек
- Макс видео: 60 сек

На CPU (i7-8700K):
- 5-секундное видео: ~2 минуты
- Не рекомендуется для практического использования

## 🔧 Advanced

### Использование GPU память более эффективно:
```python
import torch
torch.cuda.empty_cache()  # Очистить кэш между видео
```

### Параллельная обработка (Celery):
```python
# app.py
from celery import Celery

celery = Celery('visema')

@celery.task
def generate_task(image_path, audio_path):
    # асинхронная обработка
    pass
```

### Docker:
```bash
docker build -t visema .
docker run --gpus all -p 5000:5000 visema
```

## 📚 Дополнительно

- **LivePortrait docs**: https://github.com/KwaiVGI/LivePortrait
- **Wav2Lip docs**: https://github.com/Rudrabha/Wav2Lip
- **FFmpeg docs**: https://ffmpeg.org/documentation.html
- **PyTorch docs**: https://pytorch.org/docs/stable/index.html

## ✅ Успешно!

Если всё работает - поздравляем! У вас теперь есть production-grade talking avatar.

Следующие идеи улучшений:
1. Добавить эмоции (happy, sad, angry)
2. Поддержка других языков
3. Real-time генерация (streaming)
4. Пакетная обработка видео
5. Интеграция с ChatGPT/Claude для TTS

---

**Версия**: 2.0.0  
**Обновлено**: 2024
