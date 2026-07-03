# Nhật ký thay đổi - Camera-Service

Tất cả thay đổi đáng chú ý của Camera-Service được ghi lại trong tệp này.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] - 2026-07-03

### Added
- **Module `messaging/`**: Toàn bộ module giao tiếp RabbitMQ.
  - `connection.py` - `RabbitMQConnectionManager`: Quản lý kết nối với auto-reconnect và exponential backoff.
  - `publisher.py` - `FramePublisher`: Phát hành JPEG frames lên exchange.
  - `consumer.py` - `ResultConsumer`: Tiêu thụ kết quả AI từ cả hai service.
  - `orchestrator.py` - `MessagingOrchestrator`: Điều phối toàn bộ vòng đời messaging.
- **Module `models/messages.py`**: Pydantic models cho RabbitMQ messages.
  - `FrameMessage`, `DriverResultMessage`, `SeatbeltResultMessage`.
- **Module `services/display.py`**: `DisplayOverlay` - Hiển thị OpenCV với HUD overlay.
  - Thread riêng cho cv2.imshow.
  - Overlay hiển thị Sleepy status, Seatbelt status, FPS.
- **RabbitMQ configuration** trong `core/config.py`:
  - `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_USER`, `RABBITMQ_PASS`.
  - `SEATBELT_FRAME_INTERVAL` (mặc định 600 giây).
- **RabbitMQ container** trong `docker-compose.yml`.
- **Health check dependency** cho RabbitMQ trong docker-compose.
- **Pika dependency** trong `requirements.txt`.

### Changed
- **`app/main.py`**: Lifespan cập nhật để khởi động cả `CameraManager` và `MessagingOrchestrator`.
- **`services/camera_manager.py`**: Thêm `set_on_frame_callback()` và gọi callback trong `_capture_loop()`.
- **`core/config.py`**: Thêm các biến cấu hình RabbitMQ và Seatbelt interval.
- **`Dockerfile`**: Cập nhật CMD chạy uvicorn module, thêm `SEATBELT_FRAME_INTERVAL`.
- **`requirements.txt`**: Thêm `pika==1.3.2`.

### Deprecated
- **`desktop_monitor.py`**: Không còn được sử dụng. Chức năng hiển thị đã được tích hợp vào `services/display.py`.

### Removed
- (Không xóa file nào - giữ lại để tham khảo)

---

## [1.1.0] - 2025

### Added
- CameraManager với background capture thread.
- Mã hóa JPEG tự động.
- API endpoints: `/health`, `/frame`, `/info`, `/stats`.
- Docker support.
- Structured logging với CameraLogger.

---

## [1.0.0] - 2025

### Added
- Phiên bản đầu tiên.
- FastAPI application skeleton.
- Kết nối webcam cơ bản qua OpenCV.
- HTTP endpoint phục vụ frame.
