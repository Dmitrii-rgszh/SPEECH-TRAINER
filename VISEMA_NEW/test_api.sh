#!/bin/bash
# VISEMA 2.0 - API Test Examples
# 
# Использование:
#   1. Запустите сервер: python app.py
#   2. В другом терминале: bash test_api.sh
#
# Или выполняйте команды вручную:
#   curl -X GET http://127.0.0.1:5000/health

set -e  # Выход при ошибке

API_URL="http://127.0.0.1:5000"
TIMEOUT=60

echo "======================================"
echo "VISEMA 2.0 - API Testing"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if server is running
echo "Проверка сервера..."
if ! curl -s "${API_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}✗ Сервер не запущен${NC}"
    echo "Запустите: python app.py"
    exit 1
fi
echo -e "${GREEN}✓ Сервер доступен${NC}"
echo ""

# Test 1: Health check
echo "════════════════════════════════════════"
echo "Тест 1: Health Check"
echo "════════════════════════════════════════"
echo "Запрос:"
echo "  curl -X GET ${API_URL}/health"
echo ""
echo "Ответ:"
curl -X GET "${API_URL}/health" | jq '.' 2>/dev/null || \
  curl -X GET "${API_URL}/health" 2>/dev/null
echo ""
echo ""

# Test 2: Config
echo "════════════════════════════════════════"
echo "Тест 2: Configuration"
echo "════════════════════════════════════════"
echo "Запрос:"
echo "  curl -X GET ${API_URL}/config"
echo ""
echo "Ответ:"
curl -X GET "${API_URL}/config" | jq '.' 2>/dev/null || \
  curl -X GET "${API_URL}/config" 2>/dev/null
echo ""
echo ""

# Test 3: Generate (if test files exist)
if [ -f "test_face.jpg" ] && [ -f "test_audio.wav" ]; then
    echo "════════════════════════════════════════"
    echo "Тест 3: Generate Video"
    echo "════════════════════════════════════════"
    echo "Запрос:"
    echo "  curl -X POST ${API_URL}/generate \\"
    echo "    -F \"image=@test_face.jpg\" \\"
    echo "    -F \"audio=@test_audio.wav\""
    echo ""
    echo "Ответ:"
    
    RESPONSE=$(curl -s -X POST "${API_URL}/generate" \
      -F "image=@test_face.jpg" \
      -F "audio=@test_audio.wav")
    
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
    
    SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id' 2>/dev/null)
    
    if [ -n "$SESSION_ID" ] && [ "$SESSION_ID" != "null" ]; then
        echo ""
        echo -e "${GREEN}✓ Video generation started${NC}"
        echo "  Session ID: $SESSION_ID"
        echo ""
        
        # Poll status
        echo "Проверка статуса (каждые 2 сек, макс ${TIMEOUT} сек)..."
        elapsed=0
        while [ $elapsed -lt $TIMEOUT ]; do
            sleep 2
            elapsed=$((elapsed + 2))
            
            STATUS_RESPONSE=$(curl -s -X GET "${API_URL}/status/${SESSION_ID}")
            STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status' 2>/dev/null)
            PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress' 2>/dev/null)
            
            echo "  [$elapsed/$TIMEOUT] Status: $STATUS | Progress: $PROGRESS%"
            
            if [ "$STATUS" = "completed" ]; then
                echo -e "${GREEN}✓ Video ready!${NC}"
                echo "  Download: ${API_URL}/download/${SESSION_ID}"
                echo ""
                
                # Download if curl supports it
                if command -v wget &> /dev/null; then
                    echo "Скачивание видео..."
                    wget -q -O "output_${SESSION_ID}.mp4" "${API_URL}/download/${SESSION_ID}"
                    echo -e "${GREEN}✓ Сохранено: output_${SESSION_ID}.mp4${NC}"
                fi
                break
            elif [ "$STATUS" = "failed" ]; then
                ERROR=$(echo "$STATUS_RESPONSE" | jq -r '.error' 2>/dev/null)
                echo -e "${RED}✗ Generation failed: $ERROR${NC}"
                break
            fi
        done
    else
        echo -e "${RED}✗ Invalid response${NC}"
    fi
    echo ""
    echo ""
else
    echo -e "${YELLOW}⚠ Тестовые файлы не найдены:${NC}"
    echo "  test_face.jpg"
    echo "  test_audio.wav"
    echo ""
    echo "Создайте их или используйте свои файлы в запросах curl"
    echo ""
fi

# Test 4: Direct curl commands
echo "════════════════════════════════════════"
echo "Примеры команд для ручного тестирования"
echo "════════════════════════════════════════"
echo ""
echo "Проверка здоровья:"
echo "  curl -X GET http://127.0.0.1:5000/health"
echo ""
echo "Получить конфиг:"
echo "  curl -X GET http://127.0.0.1:5000/config"
echo ""
echo "Генерировать видео:"
echo "  curl -X POST http://127.0.0.1:5000/generate \\"
echo "    -F \"image=@your_image.jpg\" \\"
echo "    -F \"audio=@your_audio.wav\""
echo ""
echo "Проверить статус:"
echo "  curl -X GET http://127.0.0.1:5000/status/YOUR_SESSION_ID"
echo ""
echo "Скачать результат:"
echo "  curl -X GET http://127.0.0.1:5000/download/YOUR_SESSION_ID > output.mp4"
echo ""
echo "Скачать в браузере:"
echo "  http://127.0.0.1:5000/download/YOUR_SESSION_ID"
echo ""

echo "════════════════════════════════════════"
echo -e "${GREEN}✓ API Testing Complete${NC}"
echo "════════════════════════════════════════"
