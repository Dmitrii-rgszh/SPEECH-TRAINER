"""
Утилиты для работы с файлами, медиа и логированием
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional
import subprocess
import json
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class Config:
    """Конфигурация проекта"""
    PROJECT_ROOT = Path(__file__).parent.parent
    MODELS_DIR = PROJECT_ROOT / "models"
    TEMP_DIR = PROJECT_ROOT / "temp"
    OUTPUTS_DIR = PROJECT_ROOT / "outputs"
    
    # Создаём директории если их нет
    for d in [MODELS_DIR, TEMP_DIR, OUTPUTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Пути к моделям
    LIVEPORTRAIT_CKPT = MODELS_DIR / "liveportrait" / "checkpoints"
    WAV2LIP_CHECKPOINT = MODELS_DIR / "wav2lip" / "checkpoint.pth"
    
    # Параметры кодирования
    FFMPEG_ENCODING = {
        'vcodec': 'libx264',
        'pix_fmt': 'yuv420p',
        'profile': 'high',
        'level': '4.2',
        'crf': '18',
        'r': '25'
    }
    
    # GPU
    try:
        import torch
        GPU_AVAILABLE = torch.cuda.is_available()
        DEVICE = 'cuda' if GPU_AVAILABLE else 'cpu'
    except:
        GPU_AVAILABLE = False
        DEVICE = 'cpu'
    
    FP16 = True
    
    # Flask конфиг
    HOST = '127.0.0.1'
    PORT = 5000
    DEBUG = False


def check_ffmpeg():
    """Проверяет наличие FFmpeg"""
    try:
        subprocess.run(['ffmpeg', '-version'], 
                      capture_output=True, 
                      check=True)
        logger.info("✓ FFmpeg найден")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ FFmpeg не установлен или недоступен")
        logger.error("   Установите FFmpeg: https://ffmpeg.org/download.html")
        return False


def check_gpu():
    """Проверяет GPU"""
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"✓ GPU найден: {device_name} ({gpu_memory:.1f} GB)")
            return True
        else:
            logger.warning("⚠ GPU не найден, будет использован CPU (медленно)")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке GPU: {e}")
        return False


def get_temp_file(suffix: str = "") -> Path:
    """Получает путь для временного файла"""
    import uuid
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{uuid.uuid4().hex[:8]}{suffix}"
    return Config.TEMP_DIR / filename


def get_output_file(name: str) -> Path:
    """Получает путь для выходного файла"""
    return Config.OUTPUTS_DIR / name


def cleanup_temp():
    """Удаляет временные файлы"""
    if Config.TEMP_DIR.exists():
        import shutil
        for f in Config.TEMP_DIR.glob("*"):
            try:
                if f.is_file():
                    f.unlink()
                else:
                    shutil.rmtree(f)
            except Exception as e:
                logger.warning(f"Не удалось удалить {f}: {e}")


def get_media_duration(media_path: str) -> float:
    """Получает длительность медиафайла (сек)"""
    try:
        import subprocess
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1:noescapes=1',
            media_path
        ], capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Ошибка при получении длительности: {e}")
        return 0.0


def log_config():
    """Выводит конфигурацию системы"""
    logger.info("=" * 60)
    logger.info("VISEMA Production Pipeline Configuration")
    logger.info("=" * 60)
    logger.info(f"Project Root: {Config.PROJECT_ROOT}")
    logger.info(f"Models Dir: {Config.MODELS_DIR}")
    logger.info(f"Temp Dir: {Config.TEMP_DIR}")
    logger.info(f"Outputs Dir: {Config.OUTPUTS_DIR}")
    logger.info(f"FFmpeg encoding: {Config.FFMPEG_ENCODING}")
    check_gpu()
    check_ffmpeg()
    logger.info("=" * 60)


if __name__ == '__main__':
    log_config()
