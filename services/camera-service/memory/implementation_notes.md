# Ghi chú triển khai - Camera-Service

Những lưu ý quan trọng dành cho developer khi làm việc với Camera-Service.

---

## Nguyên tắc kiến trúc

### 1. KHÔNG viết RabbitMQ code trong FastAPI routes

Code RabbitMQ (publish, consume, connection) phải được đặt trong thư mục `messaging/`. Các file trong `api/` chỉ chứa route handlers và gọi đến service layer.

```
ĐÚNG:
  api/camera.py → camera_manager.latest_jpeg (property read)
  messaging/orchestrator.py → FramePublisher.publish() (messaging logic)

SAI:
  api/camera.py → pika.BlockingConnection(...) ← KHÔNG ĐƯỢC
```

### 2. KHÔNG xử lý AI trong Camera-Service

Camera-Service chỉ có một nhiệm vụ: thu nhận và phân phối khung hình. Mọi logic AI (EAR, YOLO, sliding window) đều nằm ở Driver-Service và Seatbelt-Service.

### 3. Mỗi thread một trách nhiệm

```
Camera Capture Thread  → chỉ đọc webcam + encode JPEG
Result Consumer Thread → chỉ lắng nghe RabbitMQ kết quả
Display Thread         → chỉ cv2.imshow + overlay
FastAPI Main Thread    → chỉ HTTP requests
```

### 4. Thread-safety là bắt buộc

Tất cả dữ liệu dùng chung giữa các thread phải được bảo vệ bằng `threading.Lock`. Xem `camera_manager.py` để biết cách triển khai.

### 5. Graceful shutdown theo thứ tự

Khi shutdown, phải dừng theo thứ tự:
1. Display (ngừng hiển thị)
2. Consumer (ngừng nhận kết quả)
3. Publishers (ngừng gửi frame)
4. Connection (đóng kết nối RabbitMQ)
5. Camera (giải phóng webcam)

---

## Lưu ý về RabbitMQ

### Connection vs Channel
- Mỗi service chỉ có **1 Connection** đến RabbitMQ.
- Mỗi Publisher/Consumer có **Channel riêng** từ Connection đó.
- Channel rẻ hơn Connection, có thể tạo nhiều.

### Exchange declaration
- Exchange được khai báo bởi **cả Publisher và Consumer** (idempotent).
- Nếu exchange đã tồn tại với cùng cấu hình, `exchange_declare` không làm gì.
- Nếu exchange đã tồn tại với cấu hình khác → lỗi (đây là cơ chế bảo vệ).

### Queue declaration
- Queue được khai báo bởi Consumer (ai consume thì người đó khai báo).
- Publisher không cần khai báo queue, chỉ cần exchange.
- Queue là `durable=True` - tồn tại sau khi restart RabbitMQ.

### Message persistence
- `delivery_mode=2` làm message được ghi vào disk.
- Không đảm bảo 100% không mất message (có thể mất trong buffer OS).
- Để đảm bảo tuyệt đối cần publisher confirm + consumer ack.

---

## Lưu ý về Camera

### Windows webcam
- Trên Windows, Docker không thể truy cập webcam.
- Phải chạy Camera-Service natively (không trong Docker).
- Các service khác vẫn chạy trong Docker bình thường.

### Multiple cameras
- Hiện tại chỉ hỗ trợ 1 camera (`CAMERA_INDEX`).
- Để thêm camera thứ 2, cần chạy instance thứ 2 của Camera-Service với `CAMERA_INDEX` khác.

### JPEG quality
- `JPEG_QUALITY=85` là cân bằng tốt giữa chất lượng và kích thước.
- Tăng lên 95 nếu cần chất lượng cao cho AI.
- Giảm xuống 50 nếu bandwidth hạn chế.

---

## Lưu ý về Display

### OpenCV window
- `cv2.imshow` chỉ hoạt động khi có display server (X11/Wayland trên Linux, native trên Windows).
- Trong Docker, cần mount X11 socket hoặc không dùng display.
- Trên server không có màn hình, nên set biến môi trường để tắt display.

### Keyboard control
- Phím `q` hoặc `ESC`: Thoát display (không dừng service).
- Display thread là daemon - nếu không cần hiển thị, có thể không gọi `display.start()`.

---

## Lưu ý về Testing

### Mock RabbitMQ
- Dùng `pytest-mock` để mock `pika.BlockingConnection` và `BlockingChannel`.
- Không cần RabbitMQ thật cho unit test.

### Integration test
- Cần RabbitMQ thật cho integration test.
- Dùng Docker: `docker run -d --name test-rabbitmq -p 5672:5672 rabbitmq:3.12-management-alpine`.
- Dọn dẹp sau test: `docker rm -f test-rabbitmq`.

### Webcam mock
- Mock `cv2.VideoCapture` để test CameraManager mà không cần webcam thật.
- Tạo numpy array giả làm frame test.

---

## Các file không nên sửa

| File | Lý do |
|------|-------|
| `desktop_monitor.py` | [DEPRECATED] Giữ lại để tham khảo code cũ |
| `app/utils/logger.py` | Logger đã ổn định, không cần thay đổi |
| `app/schemas/camera.py` | Schemas ổn định, chỉ thêm khi có API mới |

---

## Quy trình thêm dịch vụ AI mới

1. Thêm `FramePublisher` mới trong `MessagingOrchestrator.__init__()`.
2. Thêm routing key mới.
3. Thêm `ResultConsumer` queue mới (nếu cần nhận kết quả).
4. Cập nhật `DisplayOverlay._draw_hud()` để hiển thị kết quả mới.
5. Cập nhật documentation.
