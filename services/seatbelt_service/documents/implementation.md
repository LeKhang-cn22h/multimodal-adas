# Triển khai - Seatbelt-Service

## Cấu trúc thư mục

```
seatbelt_service/
├── Dockerfile
├── main.py                          # Root entry: uvicorn.run("app.main:app")
├── main_detection.py                # Standalone test script (giữ nguyên)
├── requirements.txt
├── best_1.pt                        # YOLO model weights
│
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   └── seatbelt.py              # Routes: /health, /check, /stats
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py                # Settings
│   ├── messaging/
│   │   ├── __init__.py
│   │   ├── connection.py            # RabbitMQConnectionManager
│   │   ├── publisher.py             # ResultPublisher
│   │   ├── consumer.py              # FrameConsumer
│   │   └── orchestrator.py          # MessagingOrchestrator
│   ├── services/
│   │   ├── __init__.py
│   │   ├── seatbelt_detector.py     # SeatbeltDetector
│   │   └── detector_instance.py     # Singleton
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── seatbelt.py              # API schemas
│   └── utils/
│       ├── __init__.py
│       └── logger.py                # Logger
├── documents/
├── memory/
├── knowledge-base/
└── tests/
```

---

## Module: `core/config.py`

### Class: `Settings`

**Thuộc tính model:**
- `MODEL_PATH` (default: `best.pt`) - Đường dẫn file YOLO.
- `CONFIDENCE_THRESHOLD` (default: `0.3`) - Ngưỡng confidence.
- `WARNING_FRAMES` (default: `10`) - Số frame để kích hoạt warning.
- `POLL_INTERVAL` (default: `3.0`) - [Giữ lại từ phiên bản cũ, không dùng].

**Thuộc tính RabbitMQ:**
- `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_USER`, `RABBITMQ_PASS`.

**Thuộc tính service:**
- `PORT` (default: `8007`), `LOG_LEVEL`, `SERVICE_NAME`.

---

## Module: `services/seatbelt_detector.py`

### Class: `SeatbeltDetector`

**Giữ nguyên từ phiên bản HTTP:**

| Phương thức | Thay đổi? | Mô tả |
|-------------|-----------|-------|
| `__init__()` | Không | Khởi tạo model path, thresholds |
| `load_model()` | Không | Tải YOLO model từ disk |
| `_decode_jpeg()` | Không | Giải mã JPEG → numpy array |
| `_run_inference()` | Không | Chạy YOLO, duyệt boxes, phát hiện seatbelt |
| `_update_stats()` | Không | Cập nhật streak, counters |
| `get_stats()` | Không | Trả về thống kê |

**Thay đổi:**

| Phương thức | Mô tả thay đổi |
|-------------|----------------|
| `_fetch_frame()` | **ĐÃ XÓA** - Không còn HTTP fetch |
| `check_frame()` | **ĐÃ XÓA** - Thay bằng `process()` |
| **Thêm mới**: `process(jpeg_bytes, frame_id, timestamp)` | Nhận JPEG bytes trực tiếp từ RabbitMQ |
| **Thêm mới**: `_build_result()` | Tạo dict kết quả chuẩn |
| **Thêm mới**: `get_latest_result()` | Cho API `/check` backward compatibility |

### Phương thức `process()`

```python
def process(self, jpeg_bytes: bytes, frame_id: int, frame_timestamp: float) -> dict:
    # 1. Kiểm tra model đã load
    # 2. Decode JPEG
    # 3. Chạy _run_inference (YOLO)
    # 4. _update_stats
    # 5. Return {frame_id, timestamp, seatbelt, confidence}
```

### Phương thức `get_latest_result()`

```python
def get_latest_result(self) -> dict:
    return {
        "seatbelt_detected": self._no_seatbelt_streak == 0,
        "no_seatbelt_streak": self._no_seatbelt_streak,
        "warning": self._no_seatbelt_streak >= self._warning_frames,
        "timestamp": time.time(),
    }
```

---

## Module: `messaging/connection.py`

### Class: `RabbitMQConnectionManager`

Giống hệt Camera-Service:
- `connect()` với exponential backoff.
- `create_channel()`.
- `close()`.
- `is_connected` property.
- `stop_event` property.

---

## Module: `messaging/publisher.py`

### Class: `ResultPublisher`

- `EXCHANGE = "adas.exchange"`, `EXCHANGE_TYPE = "topic"`.
- `ROUTING_KEY = "seatbelt.result"`.
- `publish(result: dict) -> bool`: Gửi JSON lên exchange.
- Tự động reconnect channel nếu đóng.

---

## Module: `messaging/consumer.py`

### Class: `FrameConsumer`

- `QUEUE = "seatbelt.frames"`, `ROUTING_KEY = "seatbelt.frame"`.
- Chạy trong background thread.
- `_consume_loop()`: Khai báo exchange → queue → bind → `basic_consume` → `start_consuming()`.
- `_on_frame_message()`: Đọc headers → gọi `detector.process()` → gọi `publisher.publish()`.
- `prefetch_count=1`: Xử lý tuần tự, tránh quá tải.

---

## Module: `messaging/orchestrator.py`

### Class: `MessagingOrchestrator`

Điều phối vòng đời:

**`start()`:**
1. `detector.load_model()` - tải YOLO.
2. `connection_manager.connect()` - kết nối RabbitMQ.
3. `publisher.start()` - khai báo exchange.
4. `consumer.start()` - bắt đầu consume.

**`stop()`:**
1. `consumer.stop()`.
2. `publisher.stop()`.
3. `connection_manager.close()`.

### Function: `get_orchestrator()`

Singleton pattern.

---

## RabbitMQ Lifecycle

### Khởi động
```
1. FastAPI lifespan START
2. Orchestrator.start()
   ├── SeatbeltDetector.load_model()
   │     └── YOLO("best_1.pt")
   ├── RabbitMQConnectionManager.connect()
   ├── ResultPublisher.start()
   │     └── exchange_declare("adas.exchange", "topic", durable=True)
   └── FrameConsumer.start() → thread
         ├── exchange_declare()
         ├── queue_declare("seatbelt.frames", durable=True)
         ├── queue_bind("seatbelt.frames", "adas.exchange", "seatbelt.frame")
         ├── basic_qos(prefetch_count=1)
         ├── basic_consume("seatbelt.frames", on_frame_message, auto_ack=True)
         └── channel.start_consuming() ← BLOCKING
```

### Dừng
```
1. FastAPI lifespan SHUTDOWN
2. Orchestrator.stop()
   ├── FrameConsumer.stop()
   │     ├── basic_cancel(consumer_tag)
   │     └── channel.close()
   ├── ResultPublisher.stop() → channel.close()
   └── RabbitMQConnectionManager.close() → connection.close()
```

---

## Docker

### Dockerfile

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8007 MODEL_PATH=best.pt CONFIDENCE_THRESHOLD=0.3 WARNING_FRAMES=10
EXPOSE 8007
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
```

### docker-compose.yml (trích)

```yaml
seatbelt-service:
  build:
    context: ./services/seatbelt_service
  environment:
    RABBITMQ_HOST: rabbitmq
    RABBITMQ_PORT: 5672
    MODEL_PATH: best.pt
  depends_on:
    rabbitmq:
      condition: service_healthy
  networks:
    - adas-net
```

### Lưu ý model file

- `best_1.pt` (~700MB) phải có trong thư mục `seatbelt_service/`.
- File `.pt` nằm trong `.gitignore`, cần copy thủ công hoặc download khi build.
- Model path trong Docker: `/app/best.pt` (theo `MODEL_PATH=best.pt`).
