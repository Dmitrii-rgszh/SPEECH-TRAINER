# VISEMA 2.0 - Quick Commands Reference

Все команды для быстрого запуска и тестирования.

## 📋 Содержание
1. Setup Commands
2. Server Commands
3. API Commands
4. Testing Commands
5. Troubleshooting Commands

---

## 🔧 Setup Commands

### Windows
```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Проверка системы
python check_setup.py

# 3. Скачивание LivePortrait
cd models
git clone https://github.com/KwaiVGI/LivePortrait.git liveportrait
cd liveportrait
pip install -e .
cd ..

# 4. Скачивание Wav2Lip
git clone https://github.com/Rudrabha/Wav2Lip.git wav2lip
cd wav2lip
pip install -r requirements.txt
cd ../..
```

### Linux/macOS
```bash
# 1. Установка зависимостей
pip3 install -r requirements.txt

# 2. Проверка системы
python3 check_setup.py

# 3. Скачивание моделей (см. Windows выше)
```

---

## 🚀 Server Commands

### Windows
```bash
# Простой старт
python app.py

# Или используйте скрипт
run.cmd

# Для продакшена (Gunicorn)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Linux/macOS
```bash
# Простой старт
python3 app.py

# Или используйте скрипт
chmod +x run.sh
./run.sh

# Для продакшена
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker
```bash
# Создание образа
docker build -t visema .

# Запуск контейнера
docker run --gpus all -p 5000:5000 visema

# Запуск с томами
docker run --gpus all -p 5000:5000 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/outputs:/app/outputs \
  visema
```

---

## 🌐 API Commands

### Health Check
```bash
curl -X GET http://127.0.0.1:5000/health
```

### Get Config
```bash
curl -X GET http://127.0.0.1:5000/config
```

### Generate Video (основное)
```bash
# Windows (PowerShell)
curl -X POST http://127.0.0.1:5000/generate `
  -F "image=@face.jpg" `
  -F "audio=@speech.wav"

# Linux/macOS (Bash)
curl -X POST http://127.0.0.1:5000/generate \
  -F "image=@face.jpg" \
  -F "audio=@speech.wav"
```

### Check Status
```bash
curl -X GET http://127.0.0.1:5000/status/SESSION_ID
```

### Download Result
```bash
# Windows
curl -X GET http://127.0.0.1:5000/download/SESSION_ID > output.mp4

# Linux/macOS
curl -X GET http://127.0.0.1:5000/download/SESSION_ID -o output.mp4

# Или в браузере:
http://127.0.0.1:5000/download/SESSION_ID
```

### Full Workflow (пример)
```bash
# 1. Генерировать видео и сохранить session_id
RESPONSE=$(curl -s -X POST http://127.0.0.1:5000/generate \
  -F "image=@face.jpg" \
  -F "audio=@speech.wav")
SESSION_ID=$(echo $RESPONSE | jq -r '.session_id')

# 2. Проверить статус в цикле
for i in {1..60}; do
  curl -s http://127.0.0.1:5000/status/$SESSION_ID | jq .
  sleep 1
done

# 3. Скачать результат
curl -X GET http://127.0.0.1:5000/download/$SESSION_ID -o final.mp4
```

---

## 🧪 Testing Commands

### Проверка системы
```bash
python check_setup.py
```

Проверяет:
- Python версия
- PyTorch/CUDA
- FFmpeg
- Зависимости
- Пути моделей
- LivePortrait
- Wav2Lip
- Flask app

### Тест API
```bash
# Windows
bash test_api.sh

# Linux/macOS  
chmod +x test_api.sh
./test_api.sh
```

### Проверка GPU
```bash
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

### Проверка FFmpeg
```bash
ffmpeg -version
```

### Проверка конфигурации
```bash
python -c "from pipeline.utils import log_config; log_config()"
```

---

## 🐛 Troubleshooting Commands

### Проверить логи
```bash
# Windows - просмотр последних строк
type server_log.txt | tail -50

# Linux/macOS
tail -50 server_log.txt
```

### Очистить временные файлы
```bash
# Windows PowerShell
Remove-Item temp/* -Force -Recurse

# Linux/macOS
rm -rf temp/*
```

### Переинсталляция зависимостей
```bash
# Удалить текущие
pip uninstall -r requirements.txt -y

# Переустановить
pip install -r requirements.txt
```

### Проверить PyTorch версию
```bash
python -c "import torch; print(torch.__version__)"
```

### Переустановить PyTorch с CUDA
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Очистить GPU память
```bash
python -c "import torch; torch.cuda.empty_cache(); print('GPU cleared')"
```

### Проверить все зависимости
```bash
pip list
```

### Обновить зависимости
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --upgrade
```

---

## 📊 Полезные Python команды

### Проверить GPU
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
```

### Загрузить файл медиа
```python
from pipeline.utils import get_media_duration
duration = get_media_duration("audio.wav")
print(f"Duration: {duration} seconds")
```

### Запустить LivePortrait
```python
from pipeline.liveportrait_runner import LivePortraitRunner

lp = LivePortraitRunner(device='cuda')
result = lp.run('face.jpg', duration_sec=5.0, output='output.mp4')
lp.cleanup()
print(f"Success: {result}")
```

### Запустить Wav2Lip
```python
from pipeline.wav2lip_runner import run_wav2lip

success = run_wav2lip('video.mp4', 'audio.wav', 'result.mp4')
print(f"Success: {success}")
```

### Закодировать видео
```python
from pipeline.ffmpeg_encode import FFmpegEncoder

encoder = FFmpegEncoder()
success = encoder.encode('input.mp4', 'output.mp4', audio_path='audio.wav')
print(f"Success: {success}")
```

---

## 🔗 Полезные ссылки

```bash
# Открыть веб интерфейс
start http://127.0.0.1:5000

# Или в браузере:
http://127.0.0.1:5000
```

---

## 📝 Примеры Bash скриптов

### Генерировать несколько видео
```bash
#!/bin/bash
for image in faces/*.jpg; do
  for audio in audios/*.wav; do
    echo "Processing $image + $audio"
    curl -X POST http://127.0.0.1:5000/generate \
      -F "image=@$image" \
      -F "audio=@$audio"
  done
done
```

### Мониторить статус
```bash
#!/bin/bash
SESSION_ID=$1
while true; do
  curl -s http://127.0.0.1:5000/status/$SESSION_ID | jq .
  sleep 2
done
```

### Batch обработка
```bash
#!/bin/bash
# Генерировать видео из всех пар файлов
for img in *.jpg; do
  audio="${img%.jpg}.wav"
  if [ -f "$audio" ]; then
    echo "Processing: $img + $audio"
    curl -X POST http://127.0.0.1:5000/generate \
      -F "image=@$img" \
      -F "audio=@$audio" | jq '.download_url'
  fi
done
```

---

## ⏱️ Типичная длительность операций

На RTX 3060 Ti:
```
5 sec video:     ~3.5 sec total (LP: 2s, W2L: 1s, FFmpeg: 0.5s)
30 sec video:    ~15 sec total
60 sec video:    ~30 sec total
```

На CPU (примерно 10x медленнее):
```
5 sec video:     ~35 sec
30 sec video:    ~3 минуты
60 sec video:    ~6 минут
```

---

## 🎯 Типичный workflow

```bash
# 1. Запустить систему
python app.py

# 2. В другом терминале - проверить
python check_setup.py

# 3. Генерировать видео
curl -X POST http://127.0.0.1:5000/generate \
  -F "image=@my_face.jpg" \
  -F "audio=@my_speech.wav"

# 4. Копировать session_id из ответа, например: "a1b2c3d4"

# 5. Проверить статус
curl http://127.0.0.1:5000/status/a1b2c3d4

# 6. Когда status == "completed", скачать
curl http://127.0.0.1:5000/download/a1b2c3d4 > final.mp4

# 7. Смотреть результат
final.mp4
```

---

**Version**: 2.0.0  
**Last Updated**: 2024
