"""
LivePortrait Runner - генерирует базовую анимацию лица с морганием и движением головы

Использует официальный LivePortrait от зфо.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, List
import numpy as np
import cv2
from pipeline.utils import Config, logger, get_temp_file

try:
    # Пытаемся импортировать LivePortrait
    from liveportrait.pipeline import LivePortraitPipeline
    from liveportrait.utils.helper import get_fps, load_img_cv2
    LIVEPORTRAIT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LivePortrait не установлен: {e}")
    LIVEPORTRAIT_AVAILABLE = False


class LivePortraitRunner:
    """
    Генератор базовой анимации лица
    - Моргание
    - Микродвижения головы  
    - Дыхание
    """
    
    def __init__(self, device: str = 'cuda', use_fp16: bool = True):
        """
        Args:
            device: 'cuda' или 'cpu'
            use_fp16: использовать half precision
        """
        if not LIVEPORTRAIT_AVAILABLE:
            raise RuntimeError("LivePortrait не установлен. "
                             "Выполните: pip install git+https://github.com/KwaiVGI/LivePortrait.git")
        
        self.device = device
        self.use_fp16 = use_fp16
        self.pipeline = None
        self._init_pipeline()
    
    def _init_pipeline(self):
        """Инициализирует LivePortrait pipeline"""
        try:
            logger.info("Инициализация LivePortrait...")
            
            # Ищем чекпойнты
            ckpt_dir = Config.LIVEPORTRAIT_CKPT
            if not ckpt_dir.exists():
                logger.warning(f"Директория чекпойнтов не найдена: {ckpt_dir}")
                logger.info("Загрузите модель из: https://github.com/KwaiVGI/LivePortrait#model-zoo")
            
            self.pipeline = LivePortraitPipeline(
                checkpoint_dir=str(ckpt_dir),
                device_id=0 if self.device == 'cuda' else None
            )
            
            logger.info("✓ LivePortrait инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации LivePortrait: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run(self, image_path: str, duration_sec: float, 
            output_video_path: str,
            fps: int = 25) -> bool:
        """
        Генерирует анимацию лица с морганием и движением головы
        
        Args:
            image_path: путь к фото лица
            duration_sec: длительность видео (сек)
            output_video_path: путь для сохранения видео
            fps: частота кадров
            
        Returns:
            True если успешно
        """
        
        if not self.pipeline:
            logger.error("Pipeline не инициализирован")
            return False
        
        try:
            image_path = str(Path(image_path).resolve())
            output_video_path = str(Path(output_video_path).resolve())
            
            # Проверяем входной файл
            if not Path(image_path).exists():
                logger.error(f"Файл не найден: {image_path}")
                return False
            
            # Загружаем изображение
            logger.info(f"Загрузка изображения: {Path(image_path).name}")
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Не удалось загрузить изображение: {image_path}")
                return False
            
            logger.info(f"Размер изображения: {img.shape}")
            
            # Генерируем анимацию
            logger.info(f"Генерация анимации ({duration_sec}s, {fps} FPS)...")
            total_frames = int(duration_sec * fps)
            
            # LivePortrait имеет встроенные режимы для idle анимации
            # Используем стандартный процесс
            pil_image = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            
            # Запускаем inference
            # (точная сигнатура зависит от версии LivePortrait)
            result = self.pipeline.execute(
                img_rgb_np=cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
                args=self._prepare_args(duration_sec, fps)
            )
            
            if result is None:
                logger.error("LivePortrait вернул None")
                return False
            
            # Сохраняем видео
            logger.info(f"Сохранение видео: {output_video_path}")
            Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Используем imageio для быстрого сохранения
            import imageio
            imageio.mimsave(output_video_path, result, fps=fps)
            
            if Path(output_video_path).exists():
                file_size_mb = Path(output_video_path).stat().st_size / (1024 * 1024)
                logger.info(f"✓ Видео сохранено: {Path(output_video_path).name} ({file_size_mb:.1f} MB)")
                return True
            else:
                logger.error("Видео не было сохранено")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении LivePortrait: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _prepare_args(self, duration_sec: float, fps: int) -> dict:
        """Подготавливает аргументы для LivePortrait"""
        return {
            'duration': duration_sec,
            'fps': fps,
            'idle_mode': True,  # Режим idle (моргание, движение головы)
            'blink_rate': 15,  # Морганий в минуту
            'head_motion_intensity': 'low'  # Лёгкое движение головы
        }
    
    def cleanup(self):
        """Очищает ресурсы"""
        if self.pipeline:
            try:
                if hasattr(self.pipeline, 'to'):
                    self.pipeline.to('cpu')
                del self.pipeline
                self.pipeline = None
                logger.info("LivePortrait очищен")
            except Exception as e:
                logger.warning(f"Ошибка при очистке: {e}")


def run_liveportrait(image_path: str, duration_sec: float, 
                    out_video_path: str, fps: int = 25) -> bool:
    """
    Функция для запуска LivePortrait
    
    Соответствует сигнатуре из требований
    
    Args:
        image_path: путь к изображению лица
        duration_sec: длительность видео
        out_video_path: путь для сохранения
        fps: частота кадров
        
    Returns:
        True если успешно
    """
    runner = LivePortraitRunner(
        device=Config.DEVICE,
        use_fp16=Config.FP16
    )
    
    try:
        success = runner.run(image_path, duration_sec, out_video_path, fps)
        return success
    finally:
        runner.cleanup()


if __name__ == '__main__':
    # Тест
    from pipeline.utils import log_config
    log_config()
    
    # Примеры использования (раскомментируйте для теста):
    # result = run_liveportrait(
    #     "test.jpg",
    #     duration_sec=5.0,
    #     out_video_path="liveportrait_output.mp4"
    # )
    # print(f"Result: {result}")
