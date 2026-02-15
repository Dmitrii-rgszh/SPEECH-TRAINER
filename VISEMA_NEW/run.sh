#!/bin/bash

# VISEMA 2.0 - Flask Server (Linux/macOS)
# Требует: Python 3.10+, CUDA 12.1, FFmpeg, установленные requirements

echo ""
echo "================================"
echo "VISEMA 2.0 - Flask Server"
echo "================================"
echo ""

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 не найден. Установите Python 3.10+ с https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python версия: $PYTHON_VERSION"

# Проверяем FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "WARNING: FFmpeg не найден. Видео кодирование не будет работать."
    echo "Установите FFmpeg:"
    echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
    echo "  macOS: brew install ffmpeg"
    echo "  Fedora: sudo dnf install ffmpeg"
    echo ""
fi

# Проверяем зависимости
echo "Проверка зависимостей..."
pip3 list | grep -i "flask\|torch" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Установка зависимостей из requirements.txt..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Ошибка при установке зависимостей"
        exit 1
    fi
fi

echo ""
echo "Проверка конфигурации..."
python3 -c "from pipeline.utils import log_config; log_config()"

echo ""
echo "✓ Сервер запускается..."
echo ""
echo "Откройте http://127.0.0.1:5000 в браузере"
echo ""
echo "Нажмите Ctrl+C для остановки"
echo ""

# Запуск Flask
python3 app.py
