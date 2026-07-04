# Yêu cầu - Camera-Service

## Yêu cầu nghiệp vụ

Camera-Service là điểm vào duy nhất của toàn bộ pipeline xử lý hình ảnh trong hệ thống ADAS. Dịch vụ này đảm nhận vai trò thu nhận dữ liệu thô từ camera vật lý và phân phối đến các dịch vụ AI hạ nguồn thông qua message broker.

**Mục tiêu nghiệp vụ:**

- Cung cấp luồng hình ảnh liên tục, ổn định từ webcam cho toàn bộ hệ thống ADAS.
- Đảm bảo tốc độ khung hình (FPS) của camera không bị ảnh hưởng bởi tốc độ xử lý AI của các dịch vụ khác.
- Cho phép nhiều dịch vụ AI cùng nhận dữ liệu từ một nguồn camera duy nhất.
- Hiển thị trạng thái hệ thống theo thời gian thực cho người giám sát.

## Yêu cầu chức năng

### FR-01: Khởi động camera
- **Mô tả**: Hệ thống phải có khả năng mở kết nối đến webcam và bắt đầu thu nhận khung hình.
- **Input**: Chỉ số camera (mặc định: 0).
- **Output**: Trạng thái camera đã sẵn sàng.
- **Xử lý lỗi**: Nếu camera không khả dụng, ghi log warning và thử kết nối lại trong nền.

### FR-02: Dừng camera
- **Mô tả**: Hệ thống phải giải phóng tài nguyên webcam khi dừng dịch vụ.
- **Input**: Tín hiệu shutdown.
- **Output**: Camera đã được giải phóng.

### FR-03: Thu nhận khung hình liên tục
- **Mô tả**: Vòng lặp nền (background thread) đọc khung hình từ webcam liên tục với tốc độ tối đa phần cứng hỗ trợ.
- **Input**: Luồng video từ webcam.
- **Output**: Khung hình BGR dạng numpy array.
- **Ràng buộc**: Không được block bởi bất kỳ tác vụ nào khác.

### FR-04: Mã hóa JPEG
- **Mô tả**: Mỗi khung hình sau khi đọc phải được mã hóa sang định dạng JPEG để giảm băng thông truyền tải.
- **Input**: Khung hình BGR (numpy array).
- **Output**: JPEG bytes.
- **Tham số**: JPEG quality có thể cấu hình (mặc định: 85).

### FR-05: Phát hành khung hình đến Driver-Service
- **Mô tả**: MỖI khung hình sau khi mã hóa JPEG phải được phát hành đến queue `driver.frames` thông qua RabbitMQ.
- **Routing key**: `driver.frame`
- **Tần suất**: Mỗi frame (không bỏ qua frame nào).
- **Định dạng**: Raw JPEG bytes trong body, metadata (frame_id, timestamp) trong headers.

### FR-06: Phát hành khung hình đến Seatbelt-Service
- **Mô tả**: Khung hình được phát hành đến queue `seatbelt.frames` với tần suất có thể cấu hình.
- **Routing key**: `seatbelt.frame`
- **Tần suất**: Mỗi `SEATBELT_FRAME_INTERVAL` giây (mặc định: 600 giây = 10 phút).
- **Lý do**: Seatbelt detection không yêu cầu thời gian thực, giảm tải cho hệ thống.

### FR-07: Tiêu thụ kết quả Driver
- **Mô tả**: Lắng nghe queue `driver.results` để nhận kết quả phát hiện buồn ngủ.
- **Routing key**: `driver.result`
- **Định dạng**: JSON chứa `frame_id`, `timestamp`, `sleepy`, `confidence`.

### FR-08: Tiêu thụ kết quả Seatbelt
- **Mô tả**: Lắng nghe queue `seatbelt.results` để nhận kết quả phát hiện dây an toàn.
- **Routing key**: `seatbelt.result`
- **Định dạng**: JSON chứa `frame_id`, `timestamp`, `seatbelt`, `confidence`.

### FR-09: Hiển thị OpenCV
- **Mô tả**: Hiển thị luồng camera trực tiếp qua cửa sổ `cv2.imshow`.
- **Tên cửa sổ**: "ADAS Monitor"
- **Kích thước mặc định**: 960x640
- **Điều khiển**: Phím `q` hoặc `ESC` để thoát.

### FR-10: Overlay kết quả AI
- **Mô tả**: Vẽ kết quả AI mới nhất lên khung hình hiển thị.
- **Nội dung overlay**:
  - `Sleepy : YES` hoặc `Sleepy : NO`
  - `Seatbelt : YES` hoặc `Seatbelt : NO`
  - `FPS : xx.x`
- **Vị trí**: Góc trên bên trái màn hình.

### FR-11: API Health Check
- **Endpoint**: `GET /health`
- **Response**: Trạng thái dịch vụ (`healthy` hoặc `degraded`) và trạng thái camera.

### FR-12: API Frame Retrieval
- **Endpoint**: `GET /frame`
- **Response**: JPEG bytes của khung hình mới nhất.
- **Ghi chú**: Đây là endpoint phụ trợ, không phải luồng dữ liệu chính.

### FR-13: API Info
- **Endpoint**: `GET /info`
- **Response**: Metadata khung hình: `frame_id`, `timestamp`, `width`, `height`, `fps`.

### FR-14: API Stats
- **Endpoint**: `GET /stats`
- **Response**: Thống kê runtime: `uptime`, `total_frames`, `camera_fps`.

## Yêu cầu phi chức năng

### NFR-01: Độc lập về hiệu năng
- Tốc độ FPS của camera KHÔNG được phụ thuộc vào tốc độ suy luận AI.
- Camera không bao giờ chờ đợi kết quả từ Driver-Service hoặc Seatbelt-Service.
- Nếu RabbitMQ hoặc các dịch vụ AI không khả dụng, camera vẫn tiếp tục thu nhận và hiển thị.

### NFR-02: Khả năng phục hồi (Resilience)
- Tự động kết nối lại khi mất kết nối RabbitMQ (exponential backoff: 1s → 2s → 4s → ... → 30s).
- Tự động phát hiện và kết nối lại khi webcam bị ngắt.
- Không crash khi bất kỳ thành phần nào gặp lỗi.

### NFR-03: Thread Safety
- Tất cả dữ liệu dùng chung giữa các thread phải được bảo vệ bằng lock.
- `latest_frame`, `latest_jpeg`, `frame_id`, `timestamp`, `fps` được truy cập an toàn từ nhiều thread.

### NFR-04: Khả năng mở rộng (Scalability)
- Có thể thêm dịch vụ AI mới bằng cách tạo thêm FramePublisher với routing key mới.
- Có thể thêm nhiều consumer cho cùng một queue (round-robin).
- Kiến trúc topic exchange cho phép mở rộng linh hoạt.

### NFR-05: Hiệu suất (Performance)
- Mã hóa JPEG phải nhanh, sử dụng cv2.imencode với tham số chất lượng tối ưu.
- Thời gian publish frame không được ảnh hưởng đến vòng lặp capture.
- Hiển thị OpenCV chạy ở thread riêng, không block capture.

### NFR-06: Khả năng quan sát (Observability)
- Log có cấu trúc với timestamp, log level, service name.
- Endpoint `/health` cho health check.
- Endpoint `/stats` cho monitoring.
- Endpoint `/info` cho thông tin frame hiện tại.

### NFR-07: Cấu hình linh hoạt
- Tất cả tham số có thể cấu hình qua biến môi trường.
- Không hardcode bất kỳ giá trị nào trong source code.
- Hỗ trợ file `.env` cho local development.

### NFR-08: Bảo mật
- RabbitMQ credentials được cấu hình qua biến môi trường (không hardcode).
- Không expose RabbitMQ management port ra ngoài trong production.
