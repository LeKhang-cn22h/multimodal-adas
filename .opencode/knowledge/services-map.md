# Bảng service — MULTIMODAL-ADAS

> Agent PHẢI cập nhật file này ngay khi thêm/đổi service, port, hoặc API
> endpoint mới. Đây là nguồn sự thật duy nhất cho "service nào làm gì".

| Service | Port (đề xuất) | Trách nhiệm chính | API chính | Messaging |
|---|---|---|---|---|
| ~~camera-service~~ | ~~8005~~ | **MERGED vào driver-service (ADR-006)** | — | — |
| driver-service | 8001 | Mở webcam + toàn bộ pipeline AI: Face Landmarker (478), 40-feature extraction, RF/rule-based classification. Kết quả publish qua RabbitMQ `driver.result`. | `GET /health`, `GET /stats`, `GET /frame` (debug) | **Publish**: `driver.result` (cho consumer ADAS bên ngoài) |
| lane-service | TBD | Phát hiện làn đường | TBD | Cần bổ sung khi có Tech Solution |
| vehicle-service | TBD | Thông tin/telemetry xe | TBD | Cần bổ sung khi có Tech Solution |
| frontend | TBD | Hiển thị dashboard tổng hợp | - | Gọi các service qua API Gateway hoặc trực tiếp (cần chốt trong Tech Solution) |

## Quy ước đặt port

- Mỗi service 1 port cố định, khai báo trong `docker-compose.yml` và đồng bộ
  với bảng trên. Không để 2 service trùng port trong cùng network.

## Quy ước network Docker

- Tất cả service nằm chung 1 network nội bộ (VD: `adas-net`) để gọi nhau
  qua service name, không dùng IP cứng.