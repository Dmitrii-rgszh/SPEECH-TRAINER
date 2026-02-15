"""
Проверка всех компонентов VISEMA 2.0

Выполните:
  python check_setup.py

Проверяет:
- Python версия
- PyTorch и CUDA
- FFmpeg
- Зависимости
- Пути моделей
"""

import sys
import subprocess
from pathlib import Path

def check_python():
    """Проверяет версию Python"""
    print("=" * 60)
    print("Проверка Python")
    print("=" * 60)
    
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    print(f"✓ Python: {version}")
    
    if sys.version_info < (3, 10):
        print("⚠ Требуется Python 3.10+")
        return False
    
    return True


def check_torch():
    """Проверяет PyTorch и CUDA"""
    print("\n" + "=" * 60)
    print("Проверка PyTorch/CUDA")
    print("=" * 60)
    
    try:
        import torch
        print(f"✓ PyTorch: {torch.__version__}")
        
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            cuda_version = torch.version.cuda
            
            print(f"✓ GPU: {device_name}")
            print(f"✓ CUDA: {cuda_version}")
            print(f"✓ GPU Memory: {gpu_memory:.1f} GB")
            return True
        else:
            print("⚠ GPU не найден - будет использован CPU (медленно)")
            return False
    
    except ImportError:
        print("✗ PyTorch не установлен")
        print("  pip install torch torchvision torchaudio")
        return False
    
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        return False


def check_ffmpeg():
    """Проверяет FFmpeg"""
    print("\n" + "=" * 60)
    print("Проверка FFmpeg")
    print("=" * 60)
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True,
                              timeout=5)
        
        if result.returncode == 0:
            # Парсим версию
            first_line = result.stdout.split('\n')[0]
            print(f"✓ FFmpeg: {first_line}")
            return True
        else:
            print("✗ FFmpeg не работает")
            return False
    
    except FileNotFoundError:
        print("✗ FFmpeg не установлен или не в PATH")
        print("  Windows: https://ffmpeg.org/download.html")
        print("  Linux: sudo apt-get install ffmpeg")
        print("  macOS: brew install ffmpeg")
        return False
    
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        return False


def check_dependencies():
    """Проверяет основные зависимости"""
    print("\n" + "=" * 60)
    print("Проверка зависимостей")
    print("=" * 60)
    
    packages = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
        'cv2': 'opencv-python',
        'numpy': 'numpy',
        'librosa': 'librosa',
        'scipy': 'scipy',
        'PIL': 'Pillow',
        'imageio': 'imageio',
        'tqdm': 'tqdm'
    }
    
    all_ok = True
    
    for import_name, package_name in packages.items():
        try:
            __import__(import_name)
            print(f"✓ {package_name}")
        except ImportError:
            print(f"✗ {package_name} не установлен")
            print(f"  pip install {package_name}")
            all_ok = False
    
    return all_ok


def check_models():
    """Проверяет пути к моделям"""
    print("\n" + "=" * 60)
    print("Проверка путей к моделям")
    print("=" * 60)
    
    from pipeline.utils import Config
    
    paths = {
        'Models dir': Config.MODELS_DIR,
        'Temp dir': Config.TEMP_DIR,
        'Outputs dir': Config.OUTPUTS_DIR,
        'LivePortrait': Config.LIVEPORTRAIT_CKPT,
        'Wav2Lip': Config.WAV2LIP_CHECKPOINT
    }
    
    all_ok = True
    
    for name, path in paths.items():
        if path.exists():
            print(f"✓ {name}: {path}")
        else:
            print(f"⚠ {name} не найден: {path}")
            if 'checkpoint' in str(path).lower() or 'ckpt' in str(path).lower():
                print(f"  Скачайте веса моделей (см. README.md)")
            all_ok = False
    
    return all_ok


def check_liveportrait():
    """Проверяет LivePortrait"""
    print("\n" + "=" * 60)
    print("Проверка LivePortrait")
    print("=" * 60)
    
    try:
        from pipeline.liveportrait_runner import LivePortraitRunner
        print("✓ LivePortrait импортирован")
        
        try:
            runner = LivePortraitRunner(device='cuda')
            print("✓ LivePortrait инициализирован")
            runner.cleanup()
            return True
        except Exception as e:
            print(f"⚠ Ошибка при инициализации: {e}")
            print("  Проверьте наличие весов моделей")
            return False
    
    except ImportError as e:
        print(f"✗ LivePortrait не установлен: {e}")
        print("  git clone https://github.com/KwaiVGI/LivePortrait.git models/liveportrait")
        print("  cd models/liveportrait && pip install -e .")
        return False


def check_wav2lip():
    """Проверяет Wav2Lip"""
    print("\n" + "=" * 60)
    print("Проверка Wav2Lip")
    print("=" * 60)
    
    try:
        from pipeline.wav2lip_runner import run_wav2lip
        print("✓ Wav2Lip импортирован")
        
        from pipeline.utils import Config
        if Config.WAV2LIP_CHECKPOINT.exists():
            print(f"✓ Checkpoint найден: {Config.WAV2LIP_CHECKPOINT}")
            return True
        else:
            print(f"⚠ Checkpoint не найден: {Config.WAV2LIP_CHECKPOINT}")
            print("  Скачайте из: https://github.com/Rudrabha/Wav2Lip/releases")
            return False
    
    except ImportError as e:
        print(f"✗ Wav2Lip не установлен: {e}")
        print("  git clone https://github.com/Rudrabha/Wav2Lip.git models/wav2lip")
        print("  cd models/wav2lip && pip install -r requirements.txt")
        return False


def check_flask():
    """Проверяет Flask приложение"""
    print("\n" + "=" * 60)
    print("Проверка Flask приложения")
    print("=" * 60)
    
    try:
        import app
        print("✓ Flask приложение импортировано")
        
        # Проверяем роуты
        routes = ['/health', '/config', '/generate', '/status/<id>', '/download/<id>']
        print(f"✓ Routes: {', '.join(routes)}")
        
        return True
    
    except Exception as e:
        print(f"✗ Ошибка при импорте app.py: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Главная функция проверки"""
    
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  VISEMA 2.0 - Setup Check  ".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    
    results = {
        'Python': check_python(),
        'PyTorch/CUDA': check_torch(),
        'FFmpeg': check_ffmpeg(),
        'Dependencies': check_dependencies(),
        'Model Paths': check_models(),
        'LivePortrait': check_liveportrait(),
        'Wav2Lip': check_wav2lip(),
        'Flask App': check_flask()
    }
    
    # Результаты
    print("\n" + "=" * 60)
    print("Результаты проверки")
    print("=" * 60)
    
    for name, result in results.items():
        status = "✓ OK" if result else "✗ FAIL"
        print(f"{status:8} {name}")
    
    print("\n" + "=" * 60)
    
    critical = ['Python', 'PyTorch/CUDA', 'FFmpeg', 'Dependencies']
    critical_ok = all(results[name] for name in critical)
    
    if critical_ok:
        print("✓ Основные компоненты установлены")
        print("")
        print("Следующие шаги:")
        print("1. Скачайте веса моделей (см. README.md)")
        print("2. Запустите: python run.cmd (Windows) или ./run.sh (Linux/macOS)")
        print("3. Откройте http://127.0.0.1:5000")
    else:
        print("✗ Требуются дополнительные установки (см. выше)")
    
    print("=" * 60 + "\n")


if __name__ == '__main__':
    try:
        # Fix encoding for Windows console
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        main()
    except KeyboardInterrupt:
        print("\nПроверка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\nОшибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
