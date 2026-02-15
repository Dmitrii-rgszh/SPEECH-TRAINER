#!/usr/bin/env python3
"""
VISEMA 2.0 - Quick Test
Запускает API и делает тестовый запрос
"""

import time
import requests
import subprocess
import sys
import os
from pathlib import Path
from threading import Thread

def start_server():
    """Запускает Flask сервер"""
    os.chdir(Path(__file__).parent)
    # Запускаем в текущем процессе (не в отдельном)
    from app import app
    print("▶ Запуск Flask сервера...")
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

def test_api():
    """Тестирует API endpoints"""
    
    # Ждём пока сервер запустится
    time.sleep(3)
    
    print("\n" + "="*60)
    print("VISEMA 2.0 - API Testing")
    print("="*60 + "\n")
    
    base_url = "http://127.0.0.1:5000"
    
    # Тест 1: Health check
    print("✓ Тест 1: Health Check")
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        print(f"  Status: {r.status_code}")
        print(f"  Response: {r.json()}")
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
    
    time.sleep(1)
    
    # Тест 2: Config
    print("\n✓ Тест 2: Configuration")
    try:
        r = requests.get(f"{base_url}/config", timeout=5)
        print(f"  Status: {r.status_code}")
        data = r.json()
        print(f"  Device: {data.get('device')}")
        print(f"  GPU: {data.get('gpu_available')}")
        print(f"  Max video: {data.get('max_video_duration')} sec")
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
    
    time.sleep(1)
    
    # Тест 3: Веб интерфейс
    print("\n✓ Тест 3: Web Interface")
    try:
        r = requests.get(f"{base_url}/", timeout=5)
        if r.status_code == 200 and "html" in r.text.lower():
            print(f"  ✓ Веб интерфейс доступен")
            print(f"  Открыть: {base_url}")
        else:
            print(f"  ✗ Интерфейс не работает")
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
    
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print("="*60)
    print("\nОткройте в браузере: http://127.0.0.1:5000")
    print("Загрузите: JPG/PNG изображение + WAV/MP3 аудиофайл")
    print("Нажмите: Generate Video")
    print("\nЛибо используйте curl:")
    print("  curl -X POST http://127.0.0.1:5000/generate \\")
    print("    -F 'image=@face.jpg' \\")
    print("    -F 'audio=@speech.wav'")
    print("\nНажмите Ctrl+C для остановки сервера\n")

if __name__ == '__main__':
    
    print("""
╔════════════════════════════════════════════════════╗
║                                                    ║
║   VISEMA 2.0 - Quick Test & Run                    ║
║   Talking Avatar Generator                         ║
║                                                    ║
╚════════════════════════════════════════════════════╝
    """)
    
    # Запускаем тесты в отдельном потоке
    test_thread = Thread(target=test_api, daemon=False)
    test_thread.start()
    
    # Запускаем сервер в основном потоке
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n\n✓ Сервер остановлен")
        sys.exit(0)
