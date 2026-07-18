# Tính năng - Seatbelt-Service

## F-01: Nhận khung hình từ RabbitMQ

### Mục đích
Thay thế HTTP polling bằng RabbitMQ consuming để nhận khung hình từ Camera-Service một cách bất đồng bộ.

### Chức năng
- `FrameConsumer` chạy trong background thread, lắng nghe queue `seatbelt.frames`.
- Nhận message với body là raw JPEG bytes, headers chứa `frame_id` và `timestamp`.
- `auto_ack=True` - không cần xác nhận thủ công.

### Giá trị mang lại
- Không còn polling HTTP mỗi 3 giây.
- Nhận frame ngay khi Camera-Service publish.
- Không block Camera-Service.

---

## F-02: Giải mã JPEG

### Mục đích
Chuyển đổi JPEG bytes từ RabbitMQ message thành numpy array BGR để YOLO xử lý.

### Chức năng
- Sử dụng `np.frombuffer()` + `cv2.imdecode()`.
- Static method, không phụ thuộc vào trạng thái instance.

---

## F-03: YOLO Inference (GIỮ NGUYÊN từ phiên bản cũ)

### Mục đích
Phát hiện dây an toàn và các đối tượng khác trong khung hình.

### Chức năng
- Model: `best_1.pt` (Ultralytics YOLO).
- 7 classes: cell phone, drinking, eyeglass, hands off, hands on, mask, seatbelt.
- Confidence threshold: 0.3 (có thể cấu hình).
- Logic inference **hoàn toàn không thay đổi** so với phiên bản HTTP.

### Giá trị mang lại
- Phát hiện chính xác, đã được huấn luyện và kiểm chứng.
- Không cần retrain model.

---

## F-04: Phân tích kết quả

### Mục đích
Xác định xem tài xế có thắt dây an toàn không dựa trên kết quả YOLO.

### Chức năng
- Duyệt qua tất cả boxes được phát hiện.
- Nếu có box với `class_id == 6` (seatbelt) → `has_seatbelt = True`.
- Lấy confidence cao nhất của class seatbelt.

---

## F-05: Theo dõi streak

### Mục đích
Tránh cảnh báo giả (false positive) bằng cách yêu cầu N frame liên tiếp không có seatbelt mới kích hoạt warning.

### Chức năng
- `_no_seatbelt_streak`: Đếm số frame liên tiếp không phát hiện seatbelt.
- Khi phát hiện seatbelt → reset streak về 0.
- Khi không phát hiện → streak += 1.
- `warning = True` khi streak >= `WARNING_FRAMES` (mặc định 10).

### Giá trị mang lại
- Giảm false alarm.
- Chỉ cảnh báo khi thực sự có vấn đề kéo dài.

---

## F-06: Phát hành kết quả

### Mục đích
Gửi kết quả phân tích về Camera-Service để hiển thị lên overlay.

### Chức năng
- `ResultPublisher` gửi JSON lên exchange với routing key `seatbelt.result`.
- Body: `{frame_id, timestamp, seatbelt, confidence}`.
- Delivery mode persistent.

---

## F-07: REST API

### Mục đích
Cung cấp endpoint HTTP cho giám sát và debug.

### Chức năng
| Endpoint | Mô tả |
|----------|-------|
| `GET /health` | Trạng thái model (healthy nếu YOLO đã load) |
| `GET /check` | Trạng thái phát hiện mới nhất |
| `GET /stats` | Thống kê: total_checks, seatbelt_ok_count, seatbelt_missing_count, avg_inference_ms |
