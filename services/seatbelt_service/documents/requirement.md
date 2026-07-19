# Yêu cầu - Seatbelt-Service

## Yêu cầu nghiệp vụ

Seatbelt-Service là dịch vụ AI chịu trách nhiệm phát hiện trạng thái thắt dây an toàn của tài xế thông qua phân tích hình ảnh từ camera trong xe. Dịch vụ sử dụng mô hình YOLO (You Only Look Once) để phát hiện đồng thời dây an toàn và các đối tượng khác (điện thoại, uống nước, kính, tay trên vô lăng, khẩu trang).

**Mục tiêu nghiệp vụ:**

- Phát hiện chính xác trạng thái thắt/không thắt dây an toàn.
- Cảnh báo khi tài xế không thắt dây an toàn trong N frame liên tiếp.
- Hoạt động độc lập, không block Camera-Service.

## Yêu cầu chức năng

### FR-01: Nhận khung hình từ RabbitMQ
- **Mô tả**: Tiêu thụ JPEG frames từ queue `seatbelt.frames`.
- **Input**: JPEG bytes + headers (frame_id, timestamp).
- **Tần suất**: Do Camera-Service quyết định (mặc định mỗi 600 giây).

### FR-02: Giải mã JPEG
- **Mô tả**: Chuyển JPEG bytes thành numpy array BGR để YOLO xử lý.

### FR-03: Chạy YOLO inference
- **Mô tả**: Sử dụng model `best_1.pt` để phát hiện 7 lớp đối tượng.
- **Model**: YOLO (Ultralytics).
- **Classes**: cell phone, drinking, eyeglass, hands off, hands on, mask, seatbelt.
- **Confidence threshold**: 0.3 (có thể cấu hình).

### FR-04: Phát hiện dây an toàn
- **Mô tả**: Kiểm tra xem class_id=6 (seatbelt) có xuất hiện trong kết quả detection không.

### FR-05: Theo dõi streak
- **Mô tả**: Đếm số frame liên tiếp KHÔNG phát hiện seatbelt.
- **Cảnh báo**: Khi streak >= `WARNING_FRAMES` (mặc định 10).

### FR-06: Phát hành kết quả
- **Mô tả**: Gửi JSON kết quả lên queue `seatbelt.results`.
- **Routing key**: `seatbelt.result`.
- **Nội dung**: `frame_id`, `timestamp`, `seatbelt` (bool), `confidence` (float).

### FR-07: API Health Check
- **Endpoint**: `GET /health`
- **Response**: Trạng thái dịch vụ và model.

### FR-08: API Check
- **Endpoint**: `GET /check`
- **Response**: Trạng thái phát hiện mới nhất.

### FR-09: API Stats
- **Endpoint**: `GET /stats`
- **Response**: Thống kê: tổng số lần kiểm tra, số lần OK/Missing, inference time trung bình.

## Yêu cầu phi chức năng

### NFR-01: Không thay đổi AI
- Toàn bộ logic YOLO inference, class names, confidence threshold được giữ nguyên từ phiên bản HTTP.
- Chỉ thay đổi lớp giao tiếp: HTTP → RabbitMQ.

### NFR-02: Khả năng phục hồi
- Tự động reconnect RabbitMQ với exponential backoff.
- Không crash khi không nhận được frame.

### NFR-03: Hiệu suất
- YOLO inference chạy đồng bộ trong consumer thread.
- Mỗi lần chỉ xử lý 1 frame (prefetch_count=1) để tránh quá tải.

### NFR-04: Khả năng mở rộng
- Có thể chạy nhiều instance Seatbelt-Service cùng lúc (round-robin consuming).
- Model path có thể cấu hình qua biến môi trường.

### NFR-05: Tương thích ngược
- Giữ lại API `/check` và `/stats` từ phiên bản HTTP.
- `detector_instance.py` vẫn tồn tại cho backward compatibility.
