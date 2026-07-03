# Triển khai - Camera-Service

## Cấu trúc thư mục đầy đủ

```
camera-service/
├── Dockerfile                          # Container build instructions
├── main.py                             # Root entry: uvicorn.run("app.main:app")
├── requirements.txt                    # Python dependencies
├── desktop_monitor.py                  # [DEPRECATED] Desktop dashboard (HTTP-based, thay thế bởi display.py)
│
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app với lifespan management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── camera.py                   # REST API routes
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py                   # Settings class - tất cả cấu hình từ ENV
│   │
│   ├── messaging/
│   │   ├── __init__.py
│   │   ├── connection.py               # RabbitMQConnectionManager
│   │   ├── publisher.py                # FramePublisher
│   │   ├── consumer.py                 # ResultConsumer
│   │   └── orchestrator.py             # MessagingOrchestrator
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── messages.py                 # FrameMessage, DriverResultMessage, SeatbeltResultMessage
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── camera_manager.py           # CameraManager - quản lý webcam
│   │   ├── camera_manager_instance.py  # Singleton instance
│   │   └── display.py                  # DisplayOverlay - cv2.imshow + HUD
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── camera.py                   # Pydantic schemas: HealthResponse, CameraInfoResponse, CameraStatsResponse
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py                   # CameraLogger - structured logging
│
├── documents/                          # Tài liệu chính thức
├── memory/                             # Bộ nhớ dài hạn cho AI Agent
├── knowledge-base/                     # Kiến thức ổn định cho AI Agent
└── tests/                              # Unit + Integration tests
```

---

## Module: `core/config.py`

### Class: `Settings`

Lớp cấu hình trung tâm, tất cả giá trị được đọc từ biến môi trường.

**Thuộc tính camera:**
- `CAMERA_INDEX`: Chỉ số webcam (mặc định: 0).
- `JPEG_QUALITY`: Chất lượng nén JPEG 0-100 (mặc định: 85).
- `FRAME_WIDTH`: Độ rộng frame mục tiêu (mặc định: 640).
- `FRAME_HEIGHT`: Độ cao frame mục tiêu (mặc định: 480).
- `DEFAULT_FPS`: FPS mặc định cho hiển thị (mặc định: 30).

**Thuộc tính RabbitMQ:**
- `RABBITMQ_HOST`: Hostname (mặc định: `localhost`).
- `RABBITMQ_PORT`: Port AMQP (mặc định: `5672`).
- `RABBITMQ_VHOST`: Virtual host (mặc định: `/`).
- `RABBITMQ_USER`: Username (mặc định: `guest`).
- `RABBITMQ_PASS`: Password (mặc định: `guest`).

**Thuộc tính Seatbelt throttle:**
- `SEATBELT_FRAME_INTERVAL`: Khoảng thời gian (giây) giữa các frame gửi cho Seatbelt (mặc định: `600.0`).

**Thuộc tính service:**
- `PORT`: HTTP port (mặc định: `8005`).
- `LOG_LEVEL`: Mức log (mặc định: `INFO`).
- `SERVICE_NAME`: Tên service (mặc định: `camera-service`).

### Function: `get_settings()`

Trả về singleton `Settings` được cache bởi `@lru_cache()`.

---

## Module: `services/camera_manager.py`

### Class: `CameraManager`

Quản lý toàn bộ vòng đời của webcam trong một background thread.

**Khởi tạo (`__init__`):**
- Đọc cấu hình từ `Settings`.
- Khởi tạo `threading.Lock`, `threading.Event`.
- Khởi tạo tất cả biến trạng thái về giá trị mặc định.

**Properties (thread-safe reads):**
- `latest_frame`: Bản sao của frame BGR mới nhất.
- `latest_jpeg`: JPEG bytes mới nhất.
- `frame_id`: ID tuần tự của frame hiện tại.
- `timestamp`: Unix timestamp của frame mới nhất.
- `width`, `height`: Kích thước thực tế của frame.
- `fps`: FPS tức thời (tính trên cửa sổ 5 giây).
- `is_running`: True nếu capture thread đang chạy.

**Lifecycle:**
- `start()`: Mở webcam, tạo và khởi động capture thread.
- `stop()`: Set stop_event, join thread (timeout 5s), release webcam.
- `_try_open_camera()`: Thử mở webcam, không raise exception.

**Callback:**
- `set_on_frame_callback(callback)`: Đăng ký callback được gọi mỗi khi có frame mới.
  - Signature: `(jpeg_bytes: bytes, frame_id: int, timestamp: float) -> None`.

**Stats:**
- `get_stats()`: Trả về dict `{uptime, total_frames, camera_fps}`.

**Vòng lặp capture (`_capture_loop`):**

Đây là phương thức private chạy trong background thread:

1. Kiểm tra camera có mở không, nếu không → thử reconnect.
2. Đọc frame bằng `cap.read()`.
3. Nếu đọc thất bại → continue.
4. Mã hóa JPEG bằng `cv2.imencode`.
5. Lưu `latest_frame`, `latest_jpeg`, `frame_id`, `timestamp` (có lock).
6. Gọi `on_frame_callback` nếu được đăng ký (trong try-except).
7. Cập nhật FPS (mỗi 1 giây, dùng cửa sổ 5 giây).
8. Kiểm tra `stop_event` → nếu set thì thoát.

---

## Module: `messaging/connection.py`

### Class: `RabbitMQConnectionManager`

Quản lý một kết nối duy nhất đến RabbitMQ với khả năng tự động reconnect.

**Khởi tạo:**
- Nhận tham số: `host`, `port`, `virtual_host`, `username`, `password`, `heartbeat`, `connection_attempts`, `retry_delay`.

**Properties:**
- `is_connected`: True nếu connection đang mở (thread-safe).
- `stop_event`: `threading.Event` dùng để báo hiệu dừng.

**Phương thức:**
- `connect()`: Thiết lập kết nối với retry và exponential backoff (1s → 2s → 4s → ... → 30s cap).
- `create_channel()`: Tạo channel mới từ connection hiện tại. Raise `RuntimeError` nếu chưa kết nối.
- `close()`: Set `stop_event`, đóng connection.

**Chiến lược reconnect:**
```
Thất bại → chờ 1s → thử lại
Thất bại → chờ 2s → thử lại
Thất bại → chờ 4s → thử lại
...
Thất bại → chờ 30s → thử lại
... (lặp vô hạn cho đến khi stop_event được set)
```

---

## Module: `messaging/publisher.py`

### Class: `FramePublisher`

Phát hành khung hình JPEG lên RabbitMQ exchange.

**Constants:**
- `EXCHANGE = "adas.exchange"`
- `EXCHANGE_TYPE = "topic"`

**Khởi tạo:**
- Nhận `connection_manager` và `routing_key`.
- Khởi tạo channel là None, lock cho thread-safety.

**Phương thức:**
- `start()`: Tạo channel, khai báo exchange (durable).
- `publish(jpeg_bytes, metadata)`: 
  1. Kiểm tra channel đã khởi tạo chưa.
  2. Kiểm tra channel còn mở không, nếu đóng → reconnect.
  3. Tạo `BasicProperties` với `delivery_mode=2`, `content_type="image/jpeg"`, `headers={frame_id, timestamp}`.
  4. `basic_publish` với body = raw JPEG bytes.
  5. Nếu thất bại → retry 1 lần với channel mới.
  6. Trả về `True` nếu thành công, `False` nếu thất bại.
- `stop()`: Đóng channel.
- `_reconnect_channel()`: Private - tạo channel mới và khai báo lại exchange.

---

## Module: `messaging/consumer.py`

### Class: `ResultConsumer`

Tiêu thụ kết quả AI từ RabbitMQ, chạy trong background thread.

**Constants:**
- `EXCHANGE = "adas.exchange"`
- `EXCHANGE_TYPE = "topic"`

**Khởi tạo:**
- Nhận `connection_manager`.
- Khởi tạo list `_consumer_tags`, callbacks, latest results, lock.

**Properties:**
- `latest_driver_result`: `DriverResultMessage | None` (thread-safe).
- `latest_seatbelt_result`: `SeatbeltResultMessage | None` (thread-safe).

**Callback registration:**
- `on_driver_result(callback)`: Đăng ký callback nhận `DriverResultMessage`.
- `on_seatbelt_result(callback)`: Đăng ký callback nhận `SeatbeltResultMessage`.

**Lifecycle:**
- `start()`: Tạo daemon thread chạy `_consume_loop`.
- `stop()`: Cancel tất cả consumer tags, đóng channel.

**Vòng lặp consume (`_consume_loop`):**
1. Kiểm tra kết nối → connect nếu cần.
2. Tạo channel, khai báo exchange.
3. `_setup_queue("driver.results", "driver.result", _on_driver_message)`.
4. `_setup_queue("seatbelt.results", "seatbelt.result", _on_seatbelt_message)`.
5. `channel.start_consuming()` - BLOCKING.
6. Nếu có exception → reconnect sau 2s.

**Xử lý message:**
- `_on_driver_message(body)`: Parse JSON → `DriverResultMessage`. Lưu + gọi callback.
- `_on_seatbelt_message(body)`: Parse JSON → `SeatbeltResultMessage`. Lưu + gọi callback.

---

## Module: `messaging/orchestrator.py`

### Class: `MessagingOrchestrator`

Điều phối toàn bộ vòng đời RabbitMQ trong Camera-Service.

**Khởi tạo:**
- Tạo `RabbitMQConnectionManager` từ config.
- Tạo 2 `FramePublisher` (driver, seatbelt).
- Tạo 1 `ResultConsumer`.
- Tạo 1 `DisplayOverlay`.
- Lưu `_last_seatbelt_frame_time` và `_seatbelt_interval`.

**Phương thức:**
- `start()`:
  1. `connection_manager.connect()`.
  2. `driver_publisher.start()` + `seatbelt_publisher.start()`.
  3. `camera_manager.set_on_frame_callback(_on_frame_captured)`.
  4. Đăng ký callbacks cho consumer.
  5. `consumer.start()`.
  6. `display.start()`.
- `stop()`:
  1. Gỡ callback khỏi camera_manager.
  2. `display.stop()`.
  3. `consumer.stop()`.
  4. `driver_publisher.stop()` + `seatbelt_publisher.stop()`.
  5. `connection_manager.close()`.
- `_on_frame_captured(jpeg_bytes, frame_id, timestamp)`:
  1. Tạo `FrameMessage`.
  2. `driver_publisher.publish()` - mỗi frame.
  3. Nếu `now - last >= interval`: `seatbelt_publisher.publish()`.

### Function: `get_orchestrator()`

Singleton pattern - trả về instance duy nhất của `MessagingOrchestrator`.

---

## Module: `services/display.py`

### Class: `DisplayOverlay`

Quản lý cửa sổ hiển thị OpenCV với HUD overlay.

**Constants:**
- `DISPLAY_FPS = 30`
- Colors: `GREEN`, `RED`, `BLUE`, `YELLOW`, `WHITE`, `BLACK`

**Khởi tạo:**
- Nhận `camera_manager`.
- Khởi tạo thread, stop_event, result locks, display FPS counters.

**Phương thức:**
- `update_driver_result(result)`: Cập nhật kết quả driver (thread-safe).
- `update_seatbelt_result(result)`: Cập nhật kết quả seatbelt (thread-safe).
- `start()`: Tạo và chạy display thread.
- `stop()`: Set stop_event, join thread, `cv2.destroyAllWindows()`.

**Vòng lặp hiển thị (`_display_loop`):**
1. `cv2.namedWindow("ADAS Monitor")`, resize 960x640.
2. Lấy `latest_frame` từ camera_manager.
3. Gọi `_draw_hud(frame)` để vẽ overlay.
4. `cv2.imshow()`, `cv2.waitKey(1)`.
5. Kiểm tra phím `q` hoặc ESC để thoát.
6. Duy trì ~30 FPS bằng cách sleep.

**Vẽ HUD (`_draw_hud`):**
1. Đọc `_driver_result` và `_seatbelt_result`.
2. Tạo 3 dòng text: Sleepy status, Seatbelt status, FPS.
3. Vẽ mỗi dòng bằng `_put_text_bg` (chữ trắng trên nền đen).
4. Vị trí: dòng 1 (y=30), dòng 2 (y=60), dòng 3 (y=90).

**Helper (`_put_text_bg`):**
- Static method vẽ text với background rectangle.
- Sử dụng `cv2.getTextSize` để tính kích thước text.
- Vẽ rectangle nền đen, sau đó putText chữ trắng.

---

## Module: `models/messages.py`

### Class: `FrameMessage`
- `frame_id: int` - ID tuần tự của frame.
- `timestamp: float` - Unix timestamp.

### Class: `DriverResultMessage`
- `frame_id: int` - ID frame gốc.
- `timestamp: float` - Thời điểm suy luận.
- `sleepy: bool` (default=False) - Tài xế có buồn ngủ không.
- `confidence: float` (default=0.0) - Độ tin cậy [0-1].

### Class: `SeatbeltResultMessage`
- `frame_id: int` - ID frame gốc.
- `timestamp: float` - Thời điểm suy luận.
- `seatbelt: bool` (default=False) - Có thắt dây an toàn không.
- `confidence: float` (default=0.0) - Độ tin cậy [0-1].

---

## Module: `schemas/camera.py`

### Class: `HealthResponse`
- `status: str` - `"healthy"` hoặc `"degraded"`.
- `camera: bool` - Camera có đang hoạt động không.

### Class: `CameraInfoResponse`
- `frame_id: int`, `timestamp: float`, `width: int`, `height: int`, `fps: float`.

### Class: `CameraStatsResponse`
- `uptime: float`, `total_frames: int`, `camera_fps: float`.

---

## RabbitMQ Lifecycle

### Khởi động

```
1. FastAPI lifespan bắt đầu
2. CameraManager.start()
3. MessagingOrchestrator.start()
   ├── RabbitMQConnectionManager.connect()
   │     └── Retry loop với exponential backoff
   ├── FramePublisher("driver.frame").start()
   │     ├── create_channel()
   │     └── exchange_declare("adas.exchange", "topic", durable=True)
   ├── FramePublisher("seatbelt.frame").start()
   │     ├── create_channel()
   │     └── exchange_declare("adas.exchange", "topic", durable=True)
   ├── CameraManager.set_on_frame_callback()
   ├── ResultConsumer.start() → thread mới
   │     ├── create_channel()
   │     ├── exchange_declare()
   │     ├── queue_declare("driver.results", durable=True)
   │     ├── queue_bind("driver.results", "adas.exchange", "driver.result")
   │     ├── queue_declare("seatbelt.results", durable=True)
   │     ├── queue_bind("seatbelt.results", "adas.exchange", "seatbelt.result")
   │     └── channel.start_consuming()  ← BLOCKING
   └── DisplayOverlay.start() → thread mới
```

### Dừng

```
1. FastAPI lifespan kết thúc
2. MessagingOrchestrator.stop()
   ├── CameraManager.set_on_frame_callback(None)
   ├── DisplayOverlay.stop()
   │     ├── stop_event.set()
   │     └── cv2.destroyAllWindows()
   ├── ResultConsumer.stop()
   │     ├── basic_cancel(tất cả consumer tags)
   │     └── channel.close()
   ├── FramePublisher("driver.frame").stop() → channel.close()
   ├── FramePublisher("seatbelt.frame").stop() → channel.close()
   └── RabbitMQConnectionManager.close()
         ├── stop_event.set()
         └── connection.close()
3. CameraManager.stop()
   ├── stop_event.set()
   ├── thread.join(timeout=5s)
   └── capture.release()
```

---

## Publisher Lifecycle

```
FramePublisher("driver.frame"):

START:
  channel = connection.create_channel()
  channel.exchange_declare("adas.exchange", "topic", durable=True)
  → SẴN SÀNG

PUBLISH (gọi mỗi frame):
  if not started: return False
  if channel.is_closed: reconnect_channel()
  properties = BasicProperties(delivery_mode=2, content_type="image/jpeg", headers={...})
  try:
    channel.basic_publish(exchange, routing_key, body=jpeg_bytes, properties=properties)
    → return True
  except:
    reconnect_channel()
    retry 1 lần
    → return True/False

STOP:
  channel.close()
```

---

## Consumer Lifecycle

```
ResultConsumer:

START:
  tạo thread mới
  thread chạy _consume_loop():
    while not stop_event:
      connect() nếu cần
      tạo channel
      exchange_declare()
      queue_declare("driver.results") + bind
      queue_declare("seatbelt.results") + bind
      basic_consume(queue, callback, auto_ack=True)
      channel.start_consuming()  ← BLOCKING
      → nếu exception: sleep 2s, continue

CALLBACK (cho mỗi message):
  parse JSON body
  validate với Pydantic
  lưu vào latest_result (lock)
  gọi registered callback (nếu có)

STOP:
  basic_cancel(tất cả consumer_tags)
  channel.close()
```

---

## Docker

### Dockerfile

```dockerfile
FROM python:3.11-slim

# System dependencies cho OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Environment variables
ENV PORT=8005
ENV CAMERA_INDEX=0
ENV JPEG_QUALITY=85
ENV FRAME_WIDTH=640 FRAME_HEIGHT=480
ENV DEFAULT_FPS=30
ENV LOG_LEVEL=INFO
ENV SEATBELT_FRAME_INTERVAL=600

EXPOSE 8005
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
```

### docker-compose.yml (trích đoạn)

```yaml
camera-service:
  build:
    context: ./services/camera-service
  container_name: adas-camera
  ports:
    - "8005:8005"
  environment:
    RABBITMQ_HOST: rabbitmq
    RABBITMQ_PORT: 5672
    RABBITMQ_VHOST: /
    RABBITMQ_USER: guest
    RABBITMQ_PASS: guest
    SEATBELT_FRAME_INTERVAL: ${SEATBELT_FRAME_INTERVAL:-600}
  depends_on:
    rabbitmq:
      condition: service_healthy
  networks:
    - adas-net
```

### Lưu ý về webcam trong Docker

Trên Windows, Docker không thể truy cập webcam. Camera-Service nên chạy natively:

```bash
cd services/camera-service
pip install -r requirements.txt
python main.py
```

---

## Environment Variables đầy đủ

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `CAMERA_INDEX` | `0` | Chỉ số webcam (0 = camera mặc định) |
| `JPEG_QUALITY` | `85` | Chất lượng nén JPEG (0-100) |
| `FRAME_WIDTH` | `640` | Độ rộng frame mục tiêu |
| `FRAME_HEIGHT` | `480` | Độ cao frame mục tiêu |
| `DEFAULT_FPS` | `30` | FPS hiển thị mặc định |
| `PORT` | `8005` | HTTP port |
| `LOG_LEVEL` | `INFO` | Mức log |
| `SERVICE_NAME` | `camera-service` | Tên service |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ hostname |
| `RABBITMQ_PORT` | `5672` | RabbitMQ AMQP port |
| `RABBITMQ_VHOST` | `/` | Virtual host |
| `RABBITMQ_USER` | `guest` | Username |
| `RABBITMQ_PASS` | `guest` | Password |
| `SEATBELT_FRAME_INTERVAL` | `600.0` | Khoảng cách giữa các frame seatbelt (giây) |
