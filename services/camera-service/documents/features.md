# Tính năng - Camera-Service

## F-01: Thu nhận khung hình từ Webcam

### Mục đích
Đọc luồng video liên tục từ webcam với tốc độ tối đa phần cứng hỗ trợ, cung cấp nguồn dữ liệu đầu vào cho toàn bộ hệ thống ADAS.

### Chức năng
- Mở kết nối đến webcam thông qua OpenCV `cv2.VideoCapture`.
- Chạy vòng lặp nền (daemon thread) đọc khung hình liên tục.
- Tự động thử kết nối lại nếu webcam bị ngắt.
- Cho phép cấu hình camera index, độ phân giải mục tiêu.

### Giá trị mang lại
- Cung cấp luồng dữ liệu ổn định, không bị gián đoạn.
- Tự động phục hồi khi có sự cố phần cứng.
- Độc lập với các thành phần khác trong hệ thống.

### Luồng hoạt động
```
start() → mở camera → tạo capture thread → _capture_loop()
  └── while not stop_event:
        ├── đọc frame từ camera
        ├── nếu thất bại → thử reconnect
        ├── mã hóa JPEG
        ├── lưu vào bộ nhớ (thread-safe)
        └── gọi on_frame_callback (nếu có)
```

---

## F-02: Mã hóa JPEG tối ưu

### Mục đích
Chuyển đổi khung hình BGR sang định dạng JPEG nén để giảm băng thông khi truyền qua RabbitMQ.

### Chức năng
- Sử dụng `cv2.imencode` với chất lượng JPEG có thể cấu hình (mặc định 85%).
- Mã hóa ngay trong vòng lặp capture (không trì hoãn).
- Lưu trữ cả frame gốc (BGR) và frame đã mã hóa (JPEG bytes).

### Giá trị mang lại
- Giảm kích thước dữ liệu truyền tải ~10-20 lần so với ảnh raw.
- JPEG được mã hóa sẵn, endpoint `/frame` không tốn chi phí encode.

### Luồng hoạt động
```
BGR frame (numpy array) → cv2.imencode(".jpg", frame, quality) → JPEG bytes
```

---

## F-03: Phát hành khung hình đến Driver-Service

### Mục đích
Gửi mọi khung hình đã mã hóa JPEG đến Driver-Service để phân tích trạng thái buồn ngủ của tài xế.

### Chức năng
- Sử dụng `FramePublisher` với routing key `driver.frame`.
- Body message là raw JPEG bytes.
- Headers chứa `frame_id` và `timestamp`.
- Delivery mode persistent (2) - tin nhắn tồn tại sau khi restart RabbitMQ.
- Tự động retry khi channel đóng.
- Publish non-blocking - không ảnh hưởng đến vòng lặp capture.

### Giá trị mang lại
- Driver-Service nhận được MỌI khung hình, đảm bảo sliding window hoạt động chính xác.
- Không bỏ sót khung hình nào.

### Luồng hoạt động
```
on_frame_captured(jpeg_bytes, frame_id, timestamp)
  └── FramePublisher("driver.frame").publish(jpeg_bytes, metadata)
        └── basic_publish(exchange="adas.exchange", routing_key="driver.frame", body=jpeg)
```

---

## F-04: Phát hành khung hình đến Seatbelt-Service (có điều chỉnh)

### Mục đích
Gửi khung hình đến Seatbelt-Service với tần suất thấp hơn vì phát hiện dây an toàn không yêu cầu thời gian thực.

### Chức năng
- Sử dụng `FramePublisher` với routing key `seatbelt.frame`.
- Tần suất: mỗi `SEATBELT_FRAME_INTERVAL` giây (mặc định 600 giây = 10 phút).
- Có thể cấu hình qua biến môi trường.

### Giá trị mang lại
- Giảm tải cho Seatbelt-Service và RabbitMQ.
- Tiết kiệm tài nguyên tính toán (YOLO inference).
- Vẫn đảm bảo phát hiện dây an toàn định kỳ.

### Luồng hoạt động
```
on_frame_captured(jpeg_bytes, frame_id, timestamp)
  ├── FramePublisher("driver.frame").publish(...)   ← mỗi frame
  └── if (now - last_time >= interval):
        FramePublisher("seatbelt.frame").publish(...) ← theo interval
```

---

## F-05: Tiêu thụ kết quả AI

### Mục đích
Nhận kết quả suy luận từ Driver-Service và Seatbelt-Service để hiển thị lên màn hình giám sát.

### Chức năng
- `ResultConsumer` chạy trong background thread riêng.
- Lắng nghe 2 queue: `driver.results` và `seatbelt.results`.
- Parse JSON body thành Pydantic model (`DriverResultMessage`, `SeatbeltResultMessage`).
- Lưu trữ kết quả mới nhất trong bộ nhớ (thread-safe lock).
- Gọi callback để cập nhật DisplayOverlay.

### Giá trị mang lại
- Kết quả AI được hiển thị gần như real-time trên màn hình giám sát.
- Không cần polling HTTP, giảm latency.

### Luồng hoạt động
```
ResultConsumer thread:
  basic_consume("driver.results", callback=_on_driver_message)
  basic_consume("seatbelt.results", callback=_on_seatbelt_message)

_on_driver_message(body):
  parse JSON → DriverResultMessage
  lưu vào latest_driver_result (lock)
  gọi display.update_driver_result()

_on_seatbelt_message(body):
  parse JSON → SeatbeltResultMessage
  lưu vào latest_seatbelt_result (lock)
  gọi display.update_seatbelt_result()
```

---

## F-06: Hiển thị OpenCV với Overlay HUD

### Mục đích
Cung cấp giao diện giám sát trực quan cho người vận hành, hiển thị luồng camera kèm trạng thái AI.

### Chức năng
- Chạy trong thread riêng (`display`).
- Lấy `latest_frame` từ CameraManager.
- Vẽ HUD với 3 dòng thông tin:
  - `Sleepy : YES/NO`
  - `Seatbelt : YES/NO`
  - `FPS : xx.x`
- Hiển thị qua `cv2.imshow("ADAS Monitor")`.
- Duy trì ~30 FPS hiển thị (có thể khác FPS capture).

### Giá trị mang lại
- Giám sát trực quan, dễ hiểu.
- Thread riêng → không ảnh hưởng đến capture hoặc messaging.

### Luồng hoạt động
```
Display thread loop (~30 FPS):
  frame = camera_manager.latest_frame
  frame = _draw_hud(frame)
  cv2.imshow("ADAS Monitor", frame)
  if key == 'q' or ESC → dừng
```

---

## F-07: REST API cho giám sát hệ thống

### Mục đích
Cung cấp endpoint HTTP để các công cụ giám sát và API Gateway có thể kiểm tra trạng thái dịch vụ.

### Chức năng
| Endpoint | Mô tả |
|----------|-------|
| `GET /health` | Trạng thái dịch vụ (`healthy`/`degraded`) |
| `GET /frame` | JPEG frame mới nhất |
| `GET /info` | Metadata frame hiện tại |
| `GET /stats` | Thống kê runtime (uptime, total_frames, fps) |

### Giá trị mang lại
- Tích hợp với hệ thống giám sát (health check).
- Debug dễ dàng (xem frame, stats).
- Tương thích với API Gateway hiện có.

---

## F-08: Tự động phục hồi kết nối (Auto-Reconnect)

### Mục đích
Đảm bảo hệ thống tự phục hồi khi mất kết nối RabbitMQ hoặc webcam mà không cần can thiệp thủ công.

### Chức năng
- **RabbitMQ**: Exponential backoff (1s → 2s → 4s → 8s → 16s → 30s).
- **Webcam**: Phát hiện `capture.isOpened() == False` và thử mở lại mỗi giây.
- **Channel**: Tự động tạo channel mới nếu channel hiện tại bị đóng.

### Giá trị mang lại
- Hệ thống có khả năng tự phục hồi, giảm thời gian downtime.
- Không cần restart service khi RabbitMQ restart.

---

## F-09: Graceful Shutdown

### Mục đích
Đảm bảo tất cả tài nguyên được giải phóng đúng cách khi dừng dịch vụ.

### Chức năng
- Dừng theo thứ tự: display → consumer → publishers → connection → camera.
- Mỗi thành phần có timeout riêng, tránh treo vô hạn.
- Log đầy đủ quá trình shutdown.

### Giá trị mang lại
- Không rò rỉ tài nguyên (memory, file handles, connections).
- Shutdown sạch sẽ, không để lại tiến trình zombie.
