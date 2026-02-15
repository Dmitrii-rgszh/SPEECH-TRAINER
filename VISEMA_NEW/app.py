"""
Flask приложение для генерации talking avatar видео

API:
  POST /generate - основной endpoint для генерации видео
  GET /download/<filename> - скачивание результата
  GET /status/<session_id> - статус обработки
"""

import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from functools import wraps
from typing import Tuple, Dict, Any

import numpy as np
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename
import logging

from pipeline.utils import Config, logger, log_config
from pipeline.liveportrait_runner import LivePortraitRunner
from pipeline.wav2lip_runner import run_wav2lip
from pipeline.ffmpeg_encode import FFmpegEncoder

# Инициализируем логирование
log_config()

# Создаем Flask приложение
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB макс
app.config['UPLOAD_FOLDER'] = str(Config.TEMP_DIR)

# Сессии обработки (в реальном приложении - Redis)
processing_sessions = {}

# === Утилиты ===

def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Проверяет расширение файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def create_session(request_data: Dict[str, Any]) -> str:
    """Создает сессию обработки"""
    session_id = str(uuid.uuid4())[:8]
    processing_sessions[session_id] = {
        'status': 'pending',
        'progress': 0,
        'request_data': request_data,
        'created_at': datetime.now(),
        'output_file': None,
        'error': None
    }
    logger.info(f"Создана сессия: {session_id}")
    return session_id


def update_session(session_id: str, **kwargs):
    """Обновляет сессию"""
    if session_id in processing_sessions:
        processing_sessions[session_id].update(kwargs)


def get_session(session_id: str) -> Dict[str, Any]:
    """Получает сессию"""
    return processing_sessions.get(session_id)


def require_session(f):
    """Декоратор для проверки сессии"""
    @wraps(f)
    def decorated_function():
        session_id = request.args.get('session_id')
        if not session_id or not get_session(session_id):
            return jsonify({'error': 'Invalid or missing session_id'}), 400
        return f(session_id)
    return decorated_function


# === Routes ===

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья приложения"""
    return jsonify({
        'status': 'ok',
        'device': Config.DEVICE,
        'gpu': 'available' if Config.GPU_AVAILABLE else 'unavailable'
    })


@app.route('/config', methods=['GET'])
def get_config():
    """Информация о конфигурации"""
    return jsonify({
        'max_video_duration': 30,  # секунд
        'fps': 25,
        'max_file_size': 500,  # MB
        'gpu_available': Config.GPU_AVAILABLE,
        'device': Config.DEVICE
    })


@app.route('/generate', methods=['POST'])
def generate():
    """
    Основной endpoint для генерации видео
    
    Параметры (multipart/form-data):
      - image: файл с изображением лица (jpg, png)
      - audio: файл с аудио (wav, mp3)
      - preview: bool (опционально, если только LivePortrait без Wav2Lip)
      
    Ответ:
      - session_id: идентификатор сессии
      - status: статус обработки ('pending', 'processing', 'completed', 'failed')
      - download_url: URL для скачивания (когда готово)
    """
    
    try:
        # === Валидация входных данных ===
        
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio provided'}), 400
        
        image_file = request.files['image']
        audio_file = request.files['audio']
        
        if image_file.filename == '' or audio_file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        if not allowed_file(image_file.filename, {'jpg', 'jpeg', 'png'}):
            return jsonify({'error': 'Invalid image format. Use JPG or PNG'}), 400
        
        if not allowed_file(audio_file.filename, {'wav', 'mp3', 'wav', 'ogg'}):
            return jsonify({'error': 'Invalid audio format. Use WAV or MP3'}), 400
        
        # === Создание сессии ===
        session_id = create_session({
            'image_filename': secure_filename(image_file.filename),
            'audio_filename': secure_filename(audio_file.filename),
            'preview_only': request.form.get('preview', 'false').lower() == 'true'
        })
        
        # === Сохранение временных файлов ===
        Path(Config.TEMP_DIR).mkdir(parents=True, exist_ok=True)
        
        image_path = Config.TEMP_DIR / f"{session_id}_image.png"
        audio_path = Config.TEMP_DIR / f"{session_id}_audio.wav"
        
        image_file.save(str(image_path))
        audio_file.save(str(audio_path))
        
        logger.info(f"[{session_id}] Файлы сохранены")
        update_session(session_id, status='processing', progress=10)
        
        # === Запуск обработки (в реальной системе - celery) ===
        try:
            success = _process_video(session_id, image_path, audio_path)
            
            if success:
                update_session(session_id, status='completed', progress=100)
                logger.info(f"[{session_id}] Готово")
                
                return jsonify({
                    'session_id': session_id,
                    'status': 'completed',
                    'message': 'Video generated successfully',
                    'download_url': f'/download/{session_id}'
                }), 200
            else:
                update_session(session_id, status='failed', progress=0)
                logger.error(f"[{session_id}] Ошибка обработки")
                
                return jsonify({
                    'session_id': session_id,
                    'status': 'failed',
                    'error': 'Video generation failed'
                }), 500
                
        except Exception as e:
            error_msg = str(e)
            update_session(session_id, status='failed', error=error_msg, progress=0)
            logger.error(f"[{session_id}] Исключение: {e}")
            import traceback
            traceback.print_exc()
            
            return jsonify({
                'session_id': session_id,
                'status': 'failed',
                'error': error_msg
            }), 500
        
        finally:
            # Очищаем временные файлы
            for path in [image_path, audio_path]:
                if Path(path).exists():
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    except Exception as e:
        logger.error(f"Ошибка в /generate: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/status/<session_id>', methods=['GET'])
def get_status(session_id: str):
    """Получить статус обработки"""
    
    session = get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'session_id': session_id,
        'status': session['status'],
        'progress': session['progress'],
        'error': session.get('error'),
        'created_at': session['created_at'].isoformat()
    })


@app.route('/download/<session_id>', methods=['GET'])
def download(session_id: str):
    """Скачать сгенерированное видео"""
    
    session = get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    if session['status'] != 'completed':
        return jsonify({'error': f"Video not ready. Status: {session['status']}"}), 400
    
    output_file = session.get('output_file')
    if not output_file or not Path(output_file).exists():
        return jsonify({'error': 'Output file not found'}), 404
    
    return send_file(
        output_file,
        mimetype='video/mp4',
        as_attachment=True,
        download_name=f'avatar_{session_id}.mp4'
    )


@app.route('/', methods=['GET'])
def index():
    """HTML страница для тестирования"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Talking Avatar Generator</title>
        <style>
            body { font-family: Arial; max-width: 600px; margin: 50px auto; }
            .form-group { margin: 15px 0; }
            input, button { padding: 8px; font-size: 14px; }
            button { background: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
            .status { margin-top: 20px; padding: 10px; border: 1px solid #ddd; }
            video { max-width: 100%; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>Talking Avatar Generator</h1>
        
        <form id="uploadForm">
            <div class="form-group">
                <label>Image (JPG/PNG):</label>
                <input type="file" id="imageInput" accept="image/*" required>
            </div>
            <div class="form-group">
                <label>Audio (WAV/MP3):</label>
                <input type="file" id="audioInput" accept="audio/*" required>
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="previewOnly"> Preview only (LivePortrait without lip-sync)
                </label>
            </div>
            <button type="submit">Generate Video</button>
        </form>
        
        <div id="status" class="status" style="display:none;">
            <h3>Status</h3>
            <p>Session: <span id="sessionId"></span></p>
            <p>Progress: <span id="progress">0</span>%</p>
            <p>Status: <span id="statusText">pending</span></p>
            <div id="errorDiv" style="display:none; color:red;">
                Error: <span id="errorMsg"></span>
            </div>
        </div>
        
        <video id="resultVideo" controls></video>
        
        <script>
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('image', document.getElementById('imageInput').files[0]);
                formData.append('audio', document.getElementById('audioInput').files[0]);
                
                if (document.getElementById('previewOnly').checked) {
                    formData.append('preview', 'true');
                }
                
                try {
                    const response = await fetch('/generate', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        const sessionId = data.session_id;
                        document.getElementById('status').style.display = 'block';
                        document.getElementById('sessionId').textContent = sessionId;
                        
                        // Poll status
                        const interval = setInterval(async () => {
                            const statusResp = await fetch(`/status/${sessionId}`);
                            const statusData = await statusResp.json();
                            
                            document.getElementById('progress').textContent = statusData.progress;
                            document.getElementById('statusText').textContent = statusData.status;
                            
                            if (statusData.status === 'completed') {
                                clearInterval(interval);
                                document.getElementById('resultVideo').src = `/download/${sessionId}`;
                            } else if (statusData.status === 'failed') {
                                clearInterval(interval);
                                document.getElementById('errorDiv').style.display = 'block';
                                document.getElementById('errorMsg').textContent = statusData.error;
                            }
                        }, 500);
                    } else {
                        alert('Error: ' + data.error);
                    }
                } catch (err) {
                    alert('Request failed: ' + err);
                }
            });
        </script>
    </body>
    </html>
    '''


# === Обработка видео (внутренняя функция) ===

def _process_video(session_id: str, image_path: Path, audio_path: Path) -> bool:
    """
    Основная функция обработки видео
    
    Шаги:
    1. LivePortrait: генерируем базовую анимацию из изображения
    2. Wav2Lip: синхронизируем рот с аудио
    3. FFmpeg: кодируем в финальный MP4
    """
    
    try:
        update_session(session_id, progress=15)
        
        # === Шаг 1: LivePortrait ===
        logger.info(f"[{session_id}] Запуск LivePortrait...")
        
        liveportrait = LivePortraitRunner(device=Config.DEVICE)
        lp_video = Config.TEMP_DIR / f"{session_id}_liveportrait.mp4"
        
        # Получаем длительность аудио
        from pipeline.utils import get_media_duration
        audio_duration = get_media_duration(str(audio_path))
        if audio_duration <= 0:
            logger.error(f"[{session_id}] Не удалось определить длительность аудио")
            return False
        
        lp_success = liveportrait.run(str(image_path), audio_duration, str(lp_video))
        liveportrait.cleanup()
        
        if not lp_success or not Path(lp_video).exists():
            logger.error(f"[{session_id}] LivePortrait не дал результат")
            return False
        
        logger.info(f"[{session_id}] LivePortrait готов: {lp_video.stat().st_size} bytes")
        update_session(session_id, progress=40)
        
        # === Шаг 2: Wav2Lip (опционально) ===
        session_data = get_session(session_id).get('request_data', {})
        
        if session_data.get('preview_only'):
            logger.info(f"[{session_id}] Preview mode - пропускаем Wav2Lip")
            result_video = lp_video
        else:
            logger.info(f"[{session_id}] Запуск Wav2Lip...")
            
            w2l_video = Config.TEMP_DIR / f"{session_id}_wav2lip.mp4"
            w2l_success = run_wav2lip(str(lp_video), str(audio_path), str(w2l_video))
            
            if not w2l_success or not Path(w2l_video).exists():
                logger.warning(f"[{session_id}] Wav2Lip не удался, используем LivePortrait")
                result_video = lp_video
            else:
                logger.info(f"[{session_id}] Wav2Lip готов: {w2l_video.stat().st_size} bytes")
                result_video = w2l_video
            
            # Удаляем временный файл LivePortrait
            if Path(lp_video).exists():
                try:
                    os.unlink(lp_video)
                except:
                    pass
        
        update_session(session_id, progress=70)
        
        # === Шаг 3: FFmpeg финальное кодирование ===
        logger.info(f"[{session_id}] Финальное кодирование...")
        
        Path(Config.OUTPUTS_DIR).mkdir(parents=True, exist_ok=True)
        output_file = Config.OUTPUTS_DIR / f"{session_id}.mp4"
        
        encoder = FFmpegEncoder()
        encode_success = encoder.encode(
            str(result_video), 
            str(output_file),
            audio_path=str(audio_path)
        )
        
        # Удаляем временный файл
        if Path(result_video).exists():
            try:
                os.unlink(result_video)
            except:
                pass
        
        if not encode_success or not Path(output_file).exists():
            logger.error(f"[{session_id}] Кодирование не удалось")
            return False
        
        logger.info(f"[{session_id}] Готово: {output_file.stat().st_size} bytes")
        update_session(session_id, output_file=str(output_file), progress=100)
        
        return True
        
    except Exception as e:
        logger.error(f"[{session_id}] Ошибка в _process_video: {e}")
        import traceback
        traceback.print_exc()
        return False


# === Обработка ошибок ===

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# === Запуск ===

if __name__ == '__main__':
    import sys
    
    # Проверяем необходимые компоненты
    if not Config.GPU_AVAILABLE:
        logger.warning("GPU не найден - будет использоваться CPU (медленнее)")
    
    logger.info(f"Запуск Flask на {Config.HOST}:{Config.PORT}")
    logger.info(f"Используется device: {Config.DEVICE}")
    logger.info(f"Temp dir: {Config.TEMP_DIR}")
    logger.info(f"Outputs dir: {Config.OUTPUTS_DIR}")
    
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=False,
        threaded=True
    )
