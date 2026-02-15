#!/usr/bin/env python3
"""
VISEMA 2.0 Quick Test
Создаёт тестовое изображение и аудио, затем отправляет запрос
"""

import os
import time
import requests
import numpy as np
from PIL import Image
from pathlib import Path

def create_test_image(path="test_image.png", size=(256, 256)):
    """Создаёт тестовое изображение"""
    # Создаём простое изображение с лицом (синий квадрат)
    img_array = np.ones((size[1], size[0], 3), dtype=np.uint8)
    img_array[:, :] = [100, 150, 200]  # Синий цвет
    
    # Рисуем простой "рот" (красная линия)
    img_array[200:220, 80:180] = [0, 0, 255]
    
    img = Image.fromarray(img_array)
    img.save(path)
    print(f"✓ Test image created: {path}")
    return path

def create_test_audio(path="test_audio.wav", duration=2.0, sample_rate=16000):
    """Создаёт тестовое аудио"""
    try:
        import scipy.io.wavfile as wavfile
        
        # Создаём синусоидальный сигнал
        t = np.linspace(0, duration, int(sample_rate * duration))
        freq = 440  # A4
        audio = np.sin(2 * np.pi * freq * t) * 0.3
        audio = (audio * 32767).astype(np.int16)
        
        wavfile.write(path, sample_rate, audio)
        print(f"✓ Test audio created: {path}")
        return path
    except:
        print("⚠ scipy не установлена, создаём пустой файл")
        # Fallback: создаём минимальный WAV файл
        return None

def test_api():
    """Тестирует API"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("\n" + "="*60)
    print("VISEMA 2.0 API Test")
    print("="*60 + "\n")
    
    # 1. Проверка здоровья
    print("1️⃣  Health Check...")
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        if r.status_code == 200:
            data = r.json()
            print(f"   ✓ Status: {data['status']}")
            print(f"   ✓ Device: {data['device']}")
            print(f"   ✓ GPU: {data['gpu']}")
        else:
            print(f"   ✗ Status code: {r.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    time.sleep(1)
    
    # 2. Конфигурация
    print("\n2️⃣  Configuration...")
    try:
        r = requests.get(f"{base_url}/config", timeout=5)
        if r.status_code == 200:
            data = r.json()
            print(f"   ✓ Max video duration: {data['max_video_duration']} sec")
            print(f"   ✓ Max file size: {data['max_file_size']} MB")
            print(f"   ✓ GPU available: {data['gpu_available']}")
            print(f"   ✓ FPS: {data['fps']}")
        else:
            print(f"   ✗ Status code: {r.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    time.sleep(1)
    
    # 3. Веб интерфейс
    print("\n3️⃣  Web Interface...")
    try:
        r = requests.get(f"{base_url}/", timeout=5)
        if r.status_code == 200 and "<html" in r.text.lower():
            print(f"   ✓ Web UI available at {base_url}")
            print(f"   ✓ HTML page loaded successfully")
        else:
            print(f"   ✗ Issue with web interface")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    time.sleep(1)
    
    # 4. Попытка генерировать видео (если файлы есть)
    print("\n4️⃣  Test Video Generation...")
    
    # Создаём тестовые файлы
    img_path = create_test_image()
    audio_path = create_test_audio()
    
    if img_path and audio_path:
        try:
            with open(img_path, 'rb') as img_f, open(audio_path, 'rb') as aud_f:
                files = {
                    'image': ('test.png', img_f, 'image/png'),
                    'audio': ('test.wav', aud_f, 'audio/wav')
                }
                r = requests.post(f"{base_url}/generate", files=files, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                session_id = data.get('session_id')
                status = data.get('status')
                print(f"   ✓ Request accepted")
                print(f"   ✓ Session ID: {session_id}")
                print(f"   ✓ Status: {status}")
                
                if status == "completed":
                    download_url = data.get('download_url')
                    print(f"   ✓ Download: {base_url}{download_url}")
                else:
                    print(f"   ℹ Waiting for processing...")
                    print(f"   ℹ Check status: /status/{session_id}")
            else:
                print(f"   ✗ Status code: {r.status_code}")
                print(f"   ✗ Response: {r.text[:200]}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    else:
        print("   ℹ Skipped (could not create test files)")
    
    print("\n" + "="*60)
    print("✓ API Testing Complete!")
    print("="*60)
    print(f"\nAccess the system at: {base_url}")
    print(f"Web interface: {base_url}/")
    print(f"\nTo generate video manually:")
    print(f"  curl -X POST {base_url}/generate \\")
    print(f"    -F 'image=@your_image.jpg' \\")
    print(f"    -F 'audio=@your_audio.wav'")

if __name__ == '__main__':
    test_api()
