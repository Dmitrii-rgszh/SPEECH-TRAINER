@echo off
REM VISEMA 2.0 - Запуск Flask приложения
REM Требует: Python 3.10+, CUDA 12.1, FFmpeg, установленные requirements

echo.
echo ================================
echo VISEMA 2.0 - Flask Server
echo ================================
echo.

REM Проверяем Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python не найден. Установите Python 3.10+ с https://python.org
    pause
    exit /b 1
)

REM Проверяем FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: FFmpeg не найден. Видео кодирование не будет работать.
    echo Установите FFmpeg с https://ffmpeg.org/download.html
    echo.
)

REM Проверяем/устанавливаем зависимости
echo Проверка зависимостей...
pip list | findstr /i "flask torch" >nul 2>&1
if %errorlevel% neq 0 (
    echo Установка зависимостей из requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Ошибка при установке зависимостей
        pause
        exit /b 1
    )
)

echo.
echo Проверка конфигурации...
python -c "from pipeline.utils import log_config; log_config()"

echo.
echo ✓ Сервер запускается...
echo.
echo Откройте http://127.0.0.1:5000 в браузере
echo.
echo Нажмите Ctrl+C для остановки
echo.

REM Запуск Flask
python app.py

pause
