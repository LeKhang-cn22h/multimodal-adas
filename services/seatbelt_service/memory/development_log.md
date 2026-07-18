# Nhật ký phát triển - Seatbelt-Service

## 2026-07-03

### Hoàn thành: Tích hợp RabbitMQ

**Mô tả**: Thay thế HTTP polling bằng RabbitMQ consuming. Giữ nguyên toàn bộ YOLO inference logic.

**Thay đổi**:
- Tạo module `messaging/` (connection, publisher, consumer, orchestrator).
- Sửa `SeatbeltDetector`: xóa `_fetch_frame()`, thêm `process()`.
- Giữ nguyên: `_run_inference()`, `_decode_jpeg()`, `_update_stats()`.
- Cập nhật FastAPI lifespan với orchestrator.
- Cập nhật Dockerfile và docker-compose.

**Người thực hiện**: Senior Software Architect.

---

## 2025-XX-XX

### Hoàn thành: Phiên bản HTTP

**Mô tả**: Seatbelt-Service với HTTP polling từ Camera-Service.
- YOLO model integration.
- API endpoints: /health, /check, /stats.
- `main_detection.py` standalone test script.
