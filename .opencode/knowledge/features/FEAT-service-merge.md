# FEAT-service-merge: Gộp camera-service vào driver-service (ADR-006)

## Thuộc Requirement
Không thuộc REQ cụ thể — đây là thay đổi kiến trúc từ ADR-006.

## Service
**driver-service** (chính) — hấp thụ toàn bộ chức năng của camera-service cũ.
**camera-service** (bị xoá) — toàn bộ thư mục `services/camera-service/` bị xoá khỏi project.

## Mô tả chức năng

Gộp 2 service thành 1: driver-service giờ đảm nhận CẢ việc mở webcam (trước đây là trách nhiệm của camera-service) VÀ toàn bộ pipeline AI. Không còn giao tiếp nội bộ qua RabbitMQ giữa camera và driver — thay bằng function call trực tiếp trong cùng process.

### Công việc cụ thể

1. **Dời code capture webcam** từ camera-service vào driver-service:
   - Tạo `app/services/camera_capture_service.py` trong driver-service, chứa class `CameraCaptureService` quản lý `cv2.VideoCapture` trong background thread, encode JPEG, giữ `latest_jpeg` trong RAM (theo mô hình thread-safe: `threading.Lock` bảo vệ buffer chia sẻ giữa capture thread và main thread).
   - Nối `CameraCaptureService` trực tiếp với `FatigueDetector.process()` bằng function call đồng bộ trong capture thread — mỗi khi có frame mới, gọi thẳng vào pipeline AI, không qua queue nội bộ.

2. **Xoá messaging nội bộ không còn dùng**:
   - Xoá `app/messaging/consumer.py` (FrameConsumer) — không còn ai consume `driver.frame`.
   - Xoá phần FramePublisher trong `app/messaging/publisher.py` (nếu có tách riêng) — không còn ai publish `driver.frame`.
   - **Giữ lại** `ResultPublisher` (publish `driver.result`) cho consumer ADAS bên ngoài.

3. **Endpoint debug**:
   - `GET /frame` — giữ lại trong driver-service (trả về `latest_jpeg` từ `CameraCaptureService`) để debug thủ công.
   - `desktop_monitor.py` (HUD hiển thị nếu có) — cần quyết định: port sang driver-service hay bỏ.

4. **Dọn dẹp project**:
   - Xoá toàn bộ thư mục `services/camera-service/`.
   - Cập nhật `docker-compose.yml`: bỏ service `camera-service`, driver-service thành container duy nhất, thêm device mapping cho webcam (`/dev/video0`).
   - Cập nhật `FEAT-messaging-refactor.md`: thu hẹp phạm vi, chỉ còn liên quan tới việc dời `ResultPublisher` vào `services/`, không còn FrameConsumer/FramePublisher.

## Acceptance Criteria

- [ ] **AC-M1**: `app/services/camera_capture_service.py` chạy background thread mở webcam, encode JPEG, giữ `latest_jpeg` (thread-safe với `threading.Lock`)
- [ ] **AC-M2**: Frame từ webcam tới pipeline AI được xử lý trong cùng process (không qua network/RabbitMQ/HTTP để truyền frame nội bộ giữa capture và inference), đảm bảo thread-safety cho cả MediaPipe và pika channel. Tech Solution quyết định cơ chế cụ thể (gọi trực tiếp đồng bộ, hay capture thread đẩy vào internal `queue.Queue` cho 1 worker thread riêng xử lý — đánh giá ưu/nhược điểm cả 2 phương án, đặc biệt xét khả năng capture bị chậm lại nếu AI xử lý không kịp tốc độ webcam).
- [ ] **AC-M3**: `GET /health` trả về thêm trạng thái webcam (`camera_connected: bool`)
- [ ] **AC-M4**: `GET /frame` (debug) trả về JPEG hiện tại từ `latest_jpeg`
- [ ] **AC-M5**: `GET /stats` giữ nguyên, bổ sung thêm FPS thực tế của webcam
- [ ] **AC-M6**: `app/messaging/consumer.py` bị xoá (không còn FrameConsumer)
- [ ] **AC-M7**: `ResultPublisher` (`app/messaging/publisher.py`) được giữ lại, publish `driver.result` như cũ
- [ ] **AC-M8**: `app/messaging/orchestrator.py` cập nhật: khởi tạo `CameraCaptureService`, start/stop trong lifecycle, không còn khởi tạo `FrameConsumer`
- [ ] **AC-M9**: Pipeline hoàn chỉnh chạy được: webcam → capture thread → FatigueDetector.process() → classifier → ResultPublisher → RabbitMQ
- [ ] **AC-M10**: Thư mục `services/camera-service/` bị xoá khỏi project
- [ ] **AC-M11**: `docker-compose.yml` cập nhật: bỏ camera-service, driver-service có device mapping cho webcam
- [ ] **AC-M12**: Không regression — test suite driver-service vẫn pass (25/25), hoặc cập nhật test cho khớp kiến trúc mới

## Độ ưu tiên

**P1** — Đây là thay đổi kiến trúc lớn, cần làm trước khi demo/chạy thật vì:
- Hiện tại driver-service không có cơ chế nhận frame (FrameConsumer consume từ RabbitMQ nhưng không có ai publish `driver.frame` sau khi gộp)
- Cần capture thread để pipeline hoạt động end-to-end

## Phụ thuộc

- **ADR-006** (đã chốt 2026-07-11): quyết định kiến trúc gộp 2 service
- **TS-rf-integration** (đã implement): pipeline AI đã hoàn chỉnh (FaceLandmarker → FeatureService → RFClassifier)
- **FEAT-messaging-refactor** (P2): cần cập nhật phạm vi sau khi merge này hoàn tất

## Câu hỏi mở (cần quyết định trong Tech Solution)

1. **Thread-safety (2 rủi ro cần xử lý đồng thời)**:
   - **MediaPipe Face Landmarker**: không thread-safe — chỉ được gọi từ 1 thread duy nhất. Nếu có 2 thread cùng gọi `detect()`, kết quả không xác định.
   - **pika (RabbitMQ client)**: yêu cầu 1 connection/channel CHỈ được dùng bởi ĐÚNG 1 thread đã tạo ra nó. Không được gọi `publish()` từ thread khác thread đã tạo channel. Vi phạm → crash hoặc corrupt dữ liệu.
   - **Yêu cầu**: kiến trúc mới phải đảm bảo CẢ MediaPipe Face Landmarker CẢ pika channel của ResultPublisher đều chỉ bị gọi từ đúng 1 thread nhất quán. Có thể là cùng 1 thread (vừa capture vừa inference vừa publish), hoặc 2 thread riêng nhưng mỗi thread chỉ đụng đúng 1 loại tài nguyên (VD: capture thread chỉ đọc webcam + ghi buffer, worker thread chạy toàn bộ pipeline AI + publish — và chỉ worker thread sở hữu pika channel). Tech Solution phải phân tích và chọn phương án.

2. **`desktop_monitor.py`**: File HUD hiển thị trong camera-service cũ — port sang driver-service hay bỏ? Nếu port, hiển thị bằng gì (OpenCV window trong capture thread, hay endpoint riêng)?

3. **`camera_client.py`**: File HTTP client trong driver-service gọi `GET /frame` của camera-service cũ — xoá luôn hay giữ lại làm tài liệu tham khảo?

4. **FPS thực tế**: Cần đo và log FPS thực tế của webcam để so sánh với `FPS_ASSUMPTION=30` — nếu lệch nhiều, cần điều chỉnh window sizes hoặc chuyển sang timestamp-based (đảo ngược ADR-005).
