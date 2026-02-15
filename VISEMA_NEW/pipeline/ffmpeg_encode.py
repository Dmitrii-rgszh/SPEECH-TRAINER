"""
FFmpeg кодировщик видео
Использует ffmpeg напрямую для кодирования без артефактов
"""

import subprocess
import logging
from pathlib import Path
from typing import Dict, Optional
from pipeline.utils import Config, logger

class FFmpegEncoder:
    """Кодирует видео с помощью FFmpeg"""
    
    def __init__(self):
        self.config = Config.FFMPEG_ENCODING
    
    def encode(self, input_path: str, output_path: str, 
               audio_path: Optional[str] = None,
               fps: int = 25,
               crf: Optional[int] = None) -> bool:
        """
        Кодирует видео в MP4
        
        Args:
            input_path: путь к входному видео
            output_path: путь к выходному MP4
            audio_path: опциональная аудиодорожка
            fps: частота кадров
            crf: качество (0-51, меньше = лучше, default 18)
            
        Returns:
            True если успешно
        """
        try:
            input_path = str(Path(input_path).resolve())
            output_path = str(Path(output_path).resolve())
            
            # Проверяем входной файл
            if not Path(input_path).exists():
                logger.error(f"Входной файл не найден: {input_path}")
                return False
            
            # Создаём директорию для выходного файла
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Собираем команду FFmpeg
            cmd = ['ffmpeg', '-i', input_path]
            
            # Добавляем аудиодорожку если есть
            if audio_path:
                if not Path(audio_path).exists():
                    logger.error(f"Аудиофайл не найден: {audio_path}")
                    return False
                cmd.extend(['-i', str(Path(audio_path).resolve())])
                cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
                cmd.extend(['-map', '0:v:0', '-map', '1:a:0'])
            
            # Видеопараметры
            cmd.extend([
                '-vcodec', self.config['vcodec'],
                '-pix_fmt', self.config['pix_fmt'],
                '-profile:v', self.config['profile'],
                '-level', self.config['level'],
                '-crf', str(crf or self.config['crf']),
                '-r', str(fps),
                '-y',  # Перезаписываем без вопросов
                output_path
            ])
            
            logger.info(f"Кодирование: {Path(input_path).name}")
            logger.debug(f"FFmpeg команда: {' '.join(cmd)}")
            
            # Запускаем FFmpeg
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True,
                                  timeout=600)  # 10 минут таймаут
            
            if result.returncode == 0:
                # Проверяем что файл создан
                if Path(output_path).exists():
                    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                    logger.info(f"✓ Видео сохранено: {Path(output_path).name} ({file_size_mb:.1f} MB)")
                    return True
                else:
                    logger.error("Файл не был создан FFmpeg")
                    return False
            else:
                logger.error(f"FFmpeg ошибка (код {result.returncode}):")
                logger.error(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Кодирование заняло слишком много времени (>10 мин)")
            return False
        except Exception as e:
            logger.error(f"Ошибка при кодировании: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_frames(self, video_path: str, output_pattern: str, 
                      fps: int = 25) -> bool:
        """
        Извлекает кадры из видео в изображения
        
        Args:
            video_path: путь к видеофайлу
            output_pattern: шаблон для сохранения (%04d.png)
            fps: частота кадров для ускорения
            
        Returns:
            True если успешно
        """
        try:
            video_path = str(Path(video_path).resolve())
            
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vf', f'fps={fps}',
                '-y',
                output_pattern
            ]
            
            logger.info(f"Извлечение кадров: {Path(video_path).name}")
            
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True,
                                  timeout=300)
            
            if result.returncode == 0:
                logger.info(f"✓ Кадры извлечены в {output_pattern}")
                return True
            else:
                logger.error(f"Ошибка при извлечении кадров: {result.stderr[-300:]}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при извлечении: {e}")
            return False
    
    def create_video_from_frames(self, input_pattern: str, output_path: str,
                                fps: int = 25, audio_path: Optional[str] = None) -> bool:
        """
        Создаёт видео из последовательности изображений
        
        Args:
            input_pattern: шаблон входных файлов (%04d.png)
            output_path: путь к выходному MP4
            fps: частота кадров
            audio_path: опциональная аудиодорожка
            
        Returns:
            True если успешно
        """
        try:
            output_path = str(Path(output_path).resolve())
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            cmd = [
                'ffmpeg',
                '-framerate', str(fps),
                '-i', input_pattern,
                '-c:v', self.config['vcodec'],
                '-pix_fmt', self.config['pix_fmt'],
                '-profile:v', self.config['profile'],
                '-level', self.config['level'],
                '-crf', self.config['crf'],
                '-y'
            ]
            
            if audio_path and Path(audio_path).exists():
                cmd.extend(['-i', str(Path(audio_path).resolve())])
                cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
                cmd.extend(['-map', '0:v:0', '-map', '1:a:0'])
            
            cmd.append(output_path)
            
            logger.info(f"Создание видео из кадров: {output_path}")
            
            result = subprocess.run(cmd,
                                  capture_output=True,
                                  text=True,
                                  timeout=600)
            
            if result.returncode == 0 and Path(output_path).exists():
                file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                logger.info(f"✓ Видео создано: {Path(output_path).name} ({file_size_mb:.1f} MB)")
                return True
            else:
                logger.error(f"Ошибка при создании видео: {result.stderr[-300:]}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return False


def encode(input_path: str, output_path: str) -> bool:
    """
    Функция для быстрого кодирования видео
    
    Соответствует сигнатуре из требований
    """
    encoder = FFmpegEncoder()
    return encoder.encode(input_path, output_path)


if __name__ == '__main__':
    # Тест
    from pipeline.utils import log_config
    log_config()
