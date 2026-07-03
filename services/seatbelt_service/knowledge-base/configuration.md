# Cấu hình - Seatbelt-Service

## Biến môi trường

### YOLO Configuration

| Biến | Mặc định  | Mô tả |
|------|-----------|-------|
| `MODEL_PATH` | `best.pt` | Đường dẫn file model YOLO |
| `CONFIDENCE_THRESHOLD` | `0.3`     | Ngưỡng confidence (0-1) |
| `WARNING_FRAMES` | `10`      | Số frame liên tiếp để kích hoạt warning |

### RabbitMQ Configuration

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `RABBITMQ_HOST` | `localhost` | Hostname (Docker: `rabbitmq`) |
| `RABBITMQ_PORT` | `5672` | AMQP port |
| `RABBITMQ_VHOST` | `/` | Virtual host |
| `RABBITMQ_USER` | `guest` | Username |
| `RABBITMQ_PASS` | `guest` | Password |

### Service Configuration

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `PORT` | `8007` | HTTP port |
| `LOG_LEVEL` | `INFO` | Mức log |
| `SERVICE_NAME` | `seatbelt-service` | Tên service |

### Deprecated

| Biến | Mặc định | Ghi chú |
|------|----------|---------|
| `POLL_INTERVAL` | `3.0` | Không còn dùng (từ phiên bản HTTP) |
| `CAMERA_SERVICE_URL` | - | Đã xóa (từ phiên bản HTTP) |
| `AGGREGATOR_URL` | - | Giữ lại nhưng không dùng |
