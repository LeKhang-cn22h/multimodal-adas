# Nhật ký thay đổi - Seatbelt-Service

## [1.2.0] - 2026-07-03

### Added
- **Module `messaging/`**: Toàn bộ module giao tiếp RabbitMQ.
  - `connection.py` - `RabbitMQConnectionManager`.
  - `publisher.py` - `ResultPublisher` (publish JSON kết quả).
  - `consumer.py` - `FrameConsumer` (consume JPEG frames).
  - `orchestrator.py` - `MessagingOrchestrator` (điều phối vòng đời).
- **Phương thức mới trong `SeatbeltDetector`**:
  - `process(jpeg_bytes, frame_id, timestamp)` - xử lý frame từ RabbitMQ.
  - `_build_result(frame_id, timestamp, seatbelt, confidence)` - tạo kết quả chuẩn.
  - `get_latest_result()` - cho API `/check` backward compatibility.
- **RabbitMQ configuration** trong `core/config.py`.
- **Pika dependency** trong `requirements.txt`.

### Changed
- **`app/main.py`**: Lifespan sử dụng `MessagingOrchestrator`.
- **`app/api/seatbelt.py`**: Routes sử dụng `get_orchestrator().detector`.
- **`app/core/config.py`**: Thêm RabbitMQ config, giữ nguyên YOLO config.
- **`services/seatbelt_detector.py`**: Thay `_fetch_frame()` (HTTP) bằng `process()` (nhận bytes).
- **`Dockerfile`**: Cập nhật CMD, thêm environment variables.

### Removed
- **`_fetch_frame()`**: HTTP polling đến Camera-Service không còn cần thiết.
- **`check_frame()`**: Thay thế bởi `process()` + `get_latest_result()`.

---

## [1.1.0] - 2025

### Added
- YOLO model loading và inference (GIỮ NGUYÊN).
- API endpoints: `/health`, `/check`, `/stats`.
- HTTP polling từ Camera-Service.
- Docker support.
- Logger.

---

## [1.0.0] - 2025

### Added
- Phiên bản đầu tiên.
- FastAPI application skeleton.
- YOLO integration.
- `main_detection.py` standalone test script.
