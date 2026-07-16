#!/bin/bash
# =====================================================================
# MULTIMODAL-ADAS — Quick Setup Script
# Chạy script này sau khi clone repo về máy
# Usage: bash scripts/setup.sh [driver|lane|vehicle|camera|gateway]
# =====================================================================

set -e
ROLE=${1:-"driver"}    # mặc định là driver nếu không truyền arg

echo "🚗 MULTIMODAL-ADAS Setup — Role: $ROLE"
echo "======================================"

# ── Check Docker ──────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "❌ Docker chưa cài. Truy cập: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker compose &>/dev/null 2>&1; then
    echo "❌ Docker Compose chưa cài (cần v2+)."
    exit 1
fi

echo "✅ Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

# ── Copy .env ─────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "📝 File .env đã được tạo từ .env.example"
    echo "   ⚠️  Hãy điền GATEWAY_HOST = IP máy mạnh vào .env trước khi chạy!"
    echo ""
fi

# ── Download face_landmarker.task nếu chưa có ─────────────────────────
TASK_FILE="services/driver-service/face_landmarker.task"
if [ ! -f "$TASK_FILE" ]; then
    echo "📥 Đang download face_landmarker.task từ Google..."
    curl -L "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" \
         -o "$TASK_FILE"
    echo "✅ face_landmarker.task downloaded."
else
    echo "✅ face_landmarker.task đã có."
fi

# ── Build và chạy theo role ───────────────────────────────────────────
echo ""
echo "🐳 Building Docker images..."

case $ROLE in
  "gateway")
    echo "   → Chạy API Gateway + Aggregator (máy mạnh)"
    docker compose -f docker-compose.gateway.yml up -d --build
    echo ""
    echo "✅ Gateway đang chạy:"
    echo "   API Gateway : http://localhost:8000"
    echo "   Aggregator  : http://localhost:8003"
    echo "   Health check: http://localhost:8000/services/health"
    ;;

  "driver")
    echo "   → Chạy Driver Service"
    # X11 forwarding cho OpenCV window
    xhost +local:docker 2>/dev/null || true
    docker compose -f docker-compose.driver.yml up -d --build
    echo ""
    echo "✅ Driver Service đang chạy trên port 8001"
    echo "   Logs: docker compose -f docker-compose.driver.yml logs -f"
    ;;

  "all")
    echo "   → Chạy toàn bộ (dev mode)"
    xhost +local:docker 2>/dev/null || true
    docker compose up -d --build
    echo ""
    echo "✅ Toàn bộ services đang chạy:"
    echo "   API Gateway : http://localhost:8000"
    echo "   Aggregator  : http://localhost:8003"
    echo "   Driver      : http://localhost:8001"
    echo "   Lane        : http://localhost:8002"
    echo "   Vehicle     : http://localhost:8004"
    echo "   Camera      : http://localhost:8005"
    ;;

  *)
    echo "❓ Role không hợp lệ: $ROLE"
    echo "   Dùng: gateway | driver | lane | vehicle | camera | all"
    exit 1
    ;;
esac

echo ""
echo "📋 Lệnh hữu ích:"
echo "   docker compose logs -f              # xem logs realtime"
echo "   docker compose ps                   # xem trạng thái containers"
echo "   docker compose down                 # dừng tất cả"
echo ""
echo "🎉 Done!"