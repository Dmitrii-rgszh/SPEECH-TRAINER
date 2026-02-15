"""
VISEMA_NEW - Production Talking Avatar Pipeline

Использует:
- LivePortrait для базовой анимации лица
- Wav2Lip для синхронизации рта с аудио
- FFmpeg для кодирования видео
"""

__version__ = "2.0.0"
__author__ = "Senior Python/ML Engineer"

from pipeline.utils import Config, logger, log_config

__all__ = [
    'Config',
    'logger',
    'log_config'
]
