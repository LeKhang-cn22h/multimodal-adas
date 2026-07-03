# Kế hoạch kiểm thử - Camera-Service

## Tổng quan

Chiến lược kiểm thử cho Camera-Service bao gồm 4 cấp độ:
1. **Unit Test**: Kiểm tra từng module độc lập với mock dependencies.
2. **Integration Test**: Kiểm tra tương tác với RabbitMQ thật.
3. **Stress Test**: Kiểm tra giới hạn hệ thống.
4. **E2E Test**: Kiểm tra toàn bộ pipeline với Docker Compose.

---

## Unit Test

### UT-CAM-001: FrameMessage Model Validation

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-001 |
| **Mục tiêu** | Kiểm tra Pydantic validation của FrameMessage |
| **Điều kiện** | Không cần dependencies ngoài |
| **Các bước** | 1. Tạo FrameMessage với frame_id=42, timestamp=123.456<br/>2. Kiểm tra các trường<br/>3. Thử tạo với thiếu trường → ValidationError<br/>4. Thử tạo với sai kiểu → ValidationError |
| **Kết quả mong đợi** | - FrameMessage hợp lệ được tạo<br/>- Thiếu trường raise ValidationError<br/>- Sai kiểu raise ValidationError |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_models.py::TestFrameMessage` |

### UT-CAM-002: DriverResultMessage Model Validation

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-002 |
| **Mục tiêu** | Kiểm tra Pydantic validation của DriverResultMessage |
| **Điều kiện** | Không cần dependencies ngoài |
| **Các bước** | 1. Tạo với sleepy=True, confidence=0.95<br/>2. Tạo với sleepy=False, confidence=0.1<br/>3. Tạo với giá trị mặc định<br/>4. Thử với JSON không hợp lệ |
| **Kết quả mong đợi** | - Các giá trị được parse đúng<br/>- Default sleepy=False, confidence=0.0 |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_models.py::TestDriverResultMessage` |

### UT-CAM-003: SeatbeltResultMessage Model Validation

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-003 |
| **Mục tiêu** | Kiểm tra Pydantic validation của SeatbeltResultMessage |
| **Điều kiện** | Không cần dependencies ngoài |
| **Các bước** | 1. Tạo với seatbelt=True, confidence=0.88<br/>2. Tạo với seatbelt=False<br/>3. Tạo với giá trị mặc định |
| **Kết quả mong đợi** | Parse chính xác, default seatbelt=False, confidence=0.0 |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_models.py::TestSeatbeltResultMessage` |

### UT-CAM-010: DisplayOverlay - Cập nhật kết quả

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-010 |
| **Mục tiêu** | Kiểm tra cập nhật kết quả driver/seatbelt |
| **Điều kiện** | Mock CameraManager |
| **Các bước** | 1. Gọi update_driver_result(DDriverResultMessage(sleepy=True))<br/>2. Gọi update_seatbelt_result(SeatbeltResultMessage(seatbelt=True))<br/>3. Kiểm tra _driver_result.sleepy == True<br/>4. Kiểm tra _seatbelt_result.seatbelt == True |
| **Kết quả mong đợi** | Kết quả được lưu chính xác |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_display.py::TestDisplayOverlay` |

### UT-CAM-011: DisplayOverlay - Vẽ HUD

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-011 |
| **Mục tiêu** | Kiểm tra _draw_hud vẽ overlay lên frame |
| **Điều kiện** | Mock CameraManager, numpy array blank |
| **Các bước** | 1. Tạo blank frame 480x640<br/>2. Cập nhật driver_result + seatbelt_result<br/>3. Gọi _draw_hud<br/>4. Kiểm tra shape output = input shape |
| **Kết quả mong đợi** | Frame output có cùng kích thước, không crash |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_display.py::TestDisplayOverlay` |

### UT-CAM-020: RabbitMQConnectionManager - Khởi tạo

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-020 |
| **Mục tiêu** | Kiểm tra khởi tạo connection manager |
| **Điều kiện** | Không cần RabbitMQ |
| **Các bước** | 1. Tạo với defaults<br/>2. Kiểm tra host=localhost, port=5672<br/>3. Kiểm tra is_connected=False<br/>4. Tạo với custom params |
| **Kết quả mong đợi** | Defaults chính xác, is_connected=False |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_connection.py` |

### UT-CAM-021: RabbitMQConnectionManager - Retry logic

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-021 |
| **Mục tiêu** | Kiểm tra retry khi kết nối thất bại |
| **Điều kiện** | Mock pika.BlockingConnection để raise exception 2 lần |
| **Các bước** | 1. Mock BlockingConnection raise AMQPConnectionError 2 lần, sau đó thành công<br/>2. Gọi connect()<br/>3. Kiểm tra số lần gọi >= 3 |
| **Kết quả mong đợi** | Retry đúng số lần, cuối cùng thành công |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_connection.py` |

### UT-CAM-030: FramePublisher - Publish success

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-030 |
| **Mục tiêu** | Kiểm tra publish frame thành công |
| **Điều kiện** | Mock RabbitMQConnectionManager |
| **Các bước** | 1. Mock connection và channel<br/>2. Gọi start()<br/>3. Gọi publish(jpeg_bytes, FrameMessage)<br/>4. Kiểm tra basic_publish được gọi 1 lần |
| **Kết quả mong đợi** | basic_publish được gọi với đúng tham số |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_messaging.py::TestFramePublisher` |

### UT-CAM-031: FramePublisher - Publish not started

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-031 |
| **Mục tiêu** | Kiểm tra publish khi chưa start |
| **Điều kiện** | Mock connection manager |
| **Các bước** | 1. Không gọi start()<br/>2. Gọi publish()<br/>3. Kiểm tra return False |
| **Kết quả mong đợi** | publish trả về False |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_messaging.py::TestFramePublisher` |

### UT-CAM-040: ResultConsumer - Parse driver JSON

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-040 |
| **Mục tiêu** | Kiểm tra parse JSON driver result |
| **Điều kiện** | Mock connection |
| **Các bước** | 1. Gọi _on_driver_message với JSON hợp lệ<br/>2. Kiểm tra latest_driver_result.frame_id = 42<br/>3. Kiểm tra latest_driver_result.sleepy = True |
| **Kết quả mong đợi** | Parse chính xác, lưu vào latest_driver_result |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_messaging.py::TestResultConsumer` |

### UT-CAM-041: ResultConsumer - Parse invalid JSON

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-041 |
| **Mục tiêu** | Kiểm tra parse JSON không hợp lệ |
| **Điều kiện** | Mock connection |
| **Các bước** | 1. Gọi _on_driver_message với body không phải JSON<br/>2. Kiểm tra latest_driver_result vẫn là None |
| **Kết quả mong đợi** | Không crash, không cập nhật result |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_messaging.py::TestResultConsumer` |

### UT-CAM-050: CameraManager - Lifecycle

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-CAM-050 |
| **Mục tiêu** | Kiểm tra start/stop CameraManager |
| **Điều kiện** | Mock cv2.VideoCapture |
| **Các bước** | 1. Mock _try_open_camera<br/>2. Gọi start() → kiểm tra is_running=True<br/>3. Gọi stop() → kiểm tra is_running=False |
| **Kết quả mong đợi** | Start/stop hoạt động đúng |
| **Kết quả thực tế** | [Đợi chạy test] |
| **File test** | `tests/test_camera_manager.py` |

---

## Integration Test

### IT-CAM-001: RabbitMQ Connection

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | IT-CAM-001 |
| **Mục tiêu** | Kiểm tra kết nối đến RabbitMQ thật |
| **Điều kiện** | RabbitMQ đang chạy trên localhost:5672 |
| **Các bước** | 1. Tạo RabbitMQConnectionManager(host="localhost")<br/>2. Gọi connect()<br/>3. Kiểm tra is_connected=True<br/>4. Gọi create_channel()<br/>5. Gọi close() |
| **Kết quả mong đợi** | Kết nối thành công, channel được tạo |
| **Kết quả thực tế** | [Đợi chạy test] |

### IT-CAM-002: Frame Publish + Consume

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | IT-CAM-002 |
| **Mục tiêu** | Kiểm tra publish frame và consume kết quả |
| **Điều kiện** | RabbitMQ đang chạy |
| **Các bước** | 1. Tạo FramePublisher("test.frame") → start<br/>2. Publish 1 frame JPEG<br/>3. Kiểm tra message xuất hiện trong queue<br/>4. Dọn dẹp |
| **Kết quả mong đợi** | Frame được publish và có thể consume |
| **Kết quả thực tế** | [Đợi chạy test] |

### IT-CAM-003: Reconnect khi RabbitMQ restart

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | IT-CAM-003 |
| **Mục tiêu** | Kiểm tra tự động reconnect khi RabbitMQ restart |
| **Điều kiện** | RabbitMQ đang chạy |
| **Các bước** | 1. Kết nối và publish frame<br/>2. Dừng RabbitMQ container<br/>3. Publish frame → return False<br/>4. Khởi động lại RabbitMQ<br/>5. Publish frame → return True |
| **Kết quả mong đợi** | Tự động reconnect và publish thành công |
| **Kết quả thực tế** | [Đợi chạy test] |

### IT-CAM-004: Overlay hiển thị

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | IT-CAM-004 |
| **Mục tiêu** | Kiểm tra overlay hiển thị đúng nội dung |
| **Điều kiện** | Camera-Service đang chạy |
| **Các bước** | 1. Publish DriverResultMessage(sleepy=True)<br/>2. Publish SeatbeltResultMessage(seatbelt=False)<br/>3. Chụp màn hình OpenCV window<br/>4. OCR kiểm tra text "Sleepy : YES", "Seatbelt : NO" |
| **Kết quả mong đợi** | Overlay hiển thị đúng trạng thái |
| **Kết quả thực tế** | [Đợi chạy test] |

---

## Stress Test

### ST-CAM-001: High FPS Publish

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | ST-CAM-001 |
| **Mục tiêu** | Kiểm tra publish ở FPS cao |
| **Điều kiện** | RabbitMQ đang chạy |
| **Các bước** | 1. Publish 60 FPS trong 30 giây (1800 frames)<br/>2. Đếm số frame publish thành công<br/>3. Kiểm tra không có frame bị mất |
| **Kết quả mong đợi** | ≥ 95% frame publish thành công |
| **Kết quả thực tế** | [Đợi chạy test] |

### ST-CAM-002: Queue Overflow

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | ST-CAM-002 |
| **Mục tiêu** | Kiểm tra khi consumer offline, queue đầy |
| **Điều kiện** | RabbitMQ đang chạy, không có consumer |
| **Các bước** | 1. Publish 10000 frame vào driver.frames<br/>2. Kiểm tra queue không bị drop<br/>3. Khởi động consumer<br/>4. Kiểm tra consumer nhận được tất cả frame |
| **Kết quả mong đợi** | Queue giữ tất cả message, consumer nhận đủ |
| **Kết quả thực tế** | [Đợi chạy test] |

### ST-CAM-003: Graceful Shutdown

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | ST-CAM-003 |
| **Mục tiêu** | Kiểm tra shutdown không crash |
| **Điều kiện** | Camera-Service đang chạy |
| **Các bước** | 1. Gửi SIGTERM đến process<br/>2. Đợi 10 giây<br/>3. Kiểm tra process đã dừng<br/>4. Kiểm tra không có resource leak |
| **Kết quả mong đợi** | Shutdown sạch, không crash, không zombie |
| **Kết quả thực tế** | [Đợi chạy test] |

---

## Docker Compose Test

### DC-CAM-001: Full Stack Startup

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | DC-CAM-001 |
| **Mục tiêu** | Kiểm tra tất cả service khởi động đúng |
| **Điều kiện** | Docker + Docker Compose |
| **Các bước** | 1. `docker-compose up -d rabbitmq driver-service seatbelt-service` (không chạy camera trong Docker)<br/>2. Chạy Camera-Service native: `cd services/camera-service && python main.py`<br/>3. Đợi 30 giây<br/>4. Gọi `curl localhost:8005/health`, `curl localhost:8001/health`, `curl localhost:8007/health` |
| **Kết quả mong đợi** | Tất cả service healthy |
| **Ghi chú** | Camera-Service không chạy trong Docker trên Windows vì không truy cập được webcam. |
| **Kết quả thực tế** | [Đợi chạy test] |

---

## Cách chạy test

```bash
# Cài đặt dependencies test
cd services/camera-service
pip install pytest pytest-cov pytest-mock

# Unit test (không cần RabbitMQ)
pytest tests/ -v --cov=app

# Integration test (cần RabbitMQ)
docker run -d --name test-rabbitmq -p 5672:5672 rabbitmq:3.12-management-alpine
RABBITMQ_HOST=localhost pytest tests/ -v -m integration

# Dọn dẹp
docker rm -f test-rabbitmq

# Tất cả test
pytest tests/ -v --cov=app --cov-report=html
```
