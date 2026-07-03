# Kế hoạch kiểm thử - Seatbelt-Service

## Unit Test

### UT-SBT-001: Decode JPEG hợp lệ

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-SBT-001 |
| **Mục tiêu** | Kiểm tra `_decode_jpeg` với JPEG hợp lệ |
| **Các bước** | 1. Tạo numpy array<br/>2. cv2.imencode → JPEG bytes<br/>3. Gọi _decode_jpeg<br/>4. Kiểm tra output.shape |
| **Kết quả mong đợi** | Output có shape (100, 100, 3) |
| **File test** | `tests/test_detector.py` |

### UT-SBT-002: Decode JPEG không hợp lệ

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-SBT-002 |
| **Mục tiêu** | Kiểm tra với bytes không phải JPEG |
| **Các bước** | 1. Gọi _decode_jpeg(b"invalid")<br/>2. Kiểm tra return |
| **Kết quả mong đợi** | Return None |
| **File test** | `tests/test_detector.py` |

### UT-SBT-010: Build result seatbelt=true

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-SBT-010 |
| **Mục tiêu** | Kiểm tra _build_result |
| **Các bước** | 1. Gọi _build_result(42, 100.0, True, 0.88)<br/>2. Kiểm tra các trường |
| **Kết quả mong đợi** | frame_id=42, timestamp=100.0, seatbelt=True, confidence=0.88 |

### UT-SBT-020: Update stats - seatbelt OK

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-SBT-020 |
| **Mục tiêu** | Kiểm tra streak reset khi phát hiện seatbelt |
| **Các bước** | 1. Set streak=5<br/>2. _update_stats(has_seatbelt=True, 50.0)<br/>3. Kiểm tra streak=0, seatbelt_ok=1 |
| **Kết quả mong đợi** | streak=0, total_checks=1 |

### UT-SBT-021: Update stats - seatbelt missing

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-SBT-021 |
| **Mục tiêu** | Kiểm tra streak tăng |
| **Các bước** | 1. Set streak=3<br/>2. _update_stats(has_seatbelt=False, 40.0)<br/>3. Kiểm tra streak=4, seatbelt_missing=1 |
| **Kết quả mong đợi** | streak=4, total_checks=1 |

### UT-SBT-030: Warning threshold

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-SBT-030 |
| **Mục tiêu** | Kiểm tra warning khi streak >= threshold |
| **Các bước** | 1. Set streak=10<br/>2. get_latest_result()<br/>3. Kiểm tra warning=True |
| **Kết quả mong đợi** | warning=True |

### UT-SBT-040: Process - no model loaded

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-SBT-040 |
| **Mục tiêu** | Kiểm tra khi model chưa load |
| **Các bước** | 1. Gọi process(jpeg, 1, 100.0) khi model=None<br/>2. Kiểm tra kết quả |
| **Kết quả mong đợi** | seatbelt=False, confidence=0.0 |

### UT-SBT-050: CLASS_NAMES đầy đủ

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | UT-SBT-050 |
| **Mục tiêu** | Kiểm tra 7 classes |
| **Các bước** | 1. Kiểm tra len(CLASS_NAMES) == 7<br/>2. Kiểm tra CLASS_NAMES[6] == "seatbelt"<br/>3. Kiểm tra SEATBELT_CLASS_ID == 6 |
| **Kết quả mong đợi** | Đúng 7 classes |

---

## Integration Test

### IT-SBT-001: Consume frame và publish result

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | IT-SBT-001 |
| **Mục tiêu** | Kiểm tra pipeline đầy đủ: consume → YOLO → publish |
| **Điều kiện** | RabbitMQ đang chạy, model best_1.pt có sẵn |
| **Các bước** | 1. Publish 1 frame JPEG vào seatbelt.frames<br/>2. Đợi consumer xử lý<br/>3. Consume từ seatbelt.results<br/>4. Kiểm tra kết quả JSON |
| **Kết quả mong đợi** | Nhận được JSON có frame_id, seatbelt (bool), confidence (float) |

### IT-SBT-002: RabbitMQ reconnect

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | IT-SBT-002 |
| **Mục tiêu** | Kiểm tra tự động reconnect |
| **Các bước** | 1. Kết nối RabbitMQ<br/>2. Dừng RabbitMQ<br/>3. Khởi động lại RabbitMQ<br/>4. Kiểm tra consumer tự kết nối lại |
| **Kết quả mong đợi** | Consumer reconnect và tiếp tục xử lý frame |

---

## Stress Test

### ST-SBT-001: High frame rate

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | ST-SBT-001 |
| **Mục tiêu** | Kiểm tra xử lý 10 frame/giây |
| **Các bước** | 1. Publish 100 frame trong 10 giây<br/>2. Kiểm tra tất cả được xử lý |
| **Kết quả mong đợi** | 100% frame được xử lý |

### ST-SBT-002: Graceful shutdown

| Thuộc tính | Giá trị |
|------------|---------|
| **Test ID** | ST-SBT-002 |
| **Mục tiêu** | Kiểm tra shutdown không crash |
| **Các bước** | 1. Gửi SIGTERM<br/>2. Đợi 10 giây<br/>3. Kiểm tra process dừng |
| **Kết quả mong đợi** | Shutdown sạch |

---

## Cách chạy

```bash
cd services/seatbelt_service
pip install pytest pytest-cov pytest-mock

# Unit test
pytest tests/ -v --cov=app

# Integration test (cần RabbitMQ)
docker run -d --name test-rabbitmq -p 5672:5672 rabbitmq:3.12-management-alpine
RABBITMQ_HOST=localhost pytest tests/ -v -m integration
docker rm -f test-rabbitmq
```
