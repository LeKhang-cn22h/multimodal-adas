# Lỗi và hạn chế đã biết - Seatbelt-Service

## KN-001: API /check không trả về detection details

**Mức độ**: Trung bình

**Mô tả**: Sau khi chuyển sang RabbitMQ, endpoint `/check` chỉ trả về trạng thái (`seatbelt_detected`, `warning`), không còn trả về danh sách detections chi tiết với bounding boxes.

**Nguyên nhân**: `get_latest_result()` chỉ lưu trạng thái, không lưu toàn bộ detection data.

**Kế hoạch sửa**: Thêm `latest_detections` vào `get_latest_result()`.

---

## KN-002: Không có health check cho RabbitMQ connection

**Mức độ**: Thấp

**Mô tả**: Endpoint `/health` chỉ kiểm tra model đã load chưa, không kiểm tra trạng thái kết nối RabbitMQ.

**Kế hoạch sửa**: Thêm `rabbitmq_connected` vào `HealthResponse`.

---

## KN-003: Model path hardcoded trong Dockerfile

**Mức độ**: Thấp

**Mô tả**: Dockerfile set `MODEL_PATH=best.pt` nhưng file model thực tế là `best_1.pt`.

**Giải pháp**: Đổi tên file model hoặc cập nhật biến môi trường.

---

## KN-004: Không hỗ trợ GPU trong Docker

**Mức độ**: Trung bình

**Mô tả**: YOLO trong Docker chạy trên CPU. Inference time ~200-500ms/frame. Với GPU có thể giảm xuống ~10-30ms.

**Kế hoạch sửa**: Thêm `nvidia-docker` support.

---

## KN-005: POLL_INTERVAL không còn sử dụng

**Mức độ**: Thấp

**Mô tả**: Biến `POLL_INTERVAL` trong config được giữ lại từ phiên bản HTTP nhưng không còn được dùng.

**Giải pháp**: Xóa hoặc đánh dấu deprecated.
