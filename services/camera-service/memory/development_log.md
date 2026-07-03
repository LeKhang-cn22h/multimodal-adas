# Nhật ký phát triển - Camera-Service

Nhật ký này ghi lại các hoạt động phát triển theo thời gian. AI Agent trong tương lai nên cập nhật tệp này khi thực hiện thay đổi.

---

## 2026-07-03

### Hoàn thành: Tích hợp RabbitMQ vào Camera-Service

**Mô tả**: Thay thế giao tiếp HTTP đồng bộ bằng RabbitMQ bất đồng bộ. Camera-Service giờ đây publish frame lên exchange và consume kết quả từ các service AI.

**Các thay đổi chính**:
- Tạo module `messaging/` với ConnectionManager, FramePublisher, ResultConsumer, Orchestrator.
- Tạo module `models/messages.py` cho message schemas.
- Tạo module `services/display.py` cho OpenCV display + overlay.
- Cập nhật `CameraManager` để hỗ trợ frame callback.
- Cập nhật `config.py` với RabbitMQ configuration.
- Cập nhật `Dockerfile` và `docker-compose.yml` với RabbitMQ container.

**Trạng thái**: Đã hoàn thành.

**Người thực hiện**: Senior Software Architect.

---

## 2025-XX-XX

### Hoàn thành: Phiên bản đầu tiên

**Mô tả**: Triển khai Camera-Service cơ bản với:
- FastAPI application.
- CameraManager với background capture thread.
- Mã hóa JPEG.
- API endpoints: /health, /frame, /info, /stats.
- Docker support.

**Trạng thái**: Đã hoàn thành.

---

## Các mục tiêu tương lai

- [ ] Hỗ trợ nhiều camera (multi-camera).
- [ ] Message TTL cho frame queue.
- [ ] Headless mode (không hiển thị OpenCV window).
- [ ] Prometheus metrics endpoint.
- [ ] GPU-accelerated JPEG encoding.
- [ ] Video recording (lưu frame vào file).
