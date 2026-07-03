# Triển khai - Camera-Service

## Docker

### Build

```bash
cd services/camera-service
docker build -t adas-camera:latest .
```

### Docker Compose

Camera-Service được định nghĩa trong `docker-compose.yml`:

```yaml
camera-service:
  build:
    context: ./services/camera-service
  container_name: adas-camera
  ports:
    - "8005:8005"
  environment:
    PORT: 8005
    CAMERA_INDEX: ${CAMERA_INDEX:-0}
    RABBITMQ_HOST: rabbitmq
    RABBITMQ_PORT: 5672
    RABBITMQ_VHOST: /
    RABBITMQ_USER: guest
    RABBITMQ_PASS: guest
    SEATBELT_FRAME_INTERVAL: ${SEATBELT_FRAME_INTERVAL:-600}
  depends_on:
    rabbitmq:
      condition: service_healthy
  networks:
    - adas-net
  restart: unless-stopped
```

### Lưu ý webcam trên Windows

Docker Desktop trên Windows **không hỗ trợ truy cập webcam**. Camera-Service nên được chạy natively:

```bash
# Windows (native)
cd services/camera-service
pip install -r requirements.txt
set RABBITMQ_HOST=localhost
python main.py
```

### Lưu ý webcam trên Linux

Trên Linux, có thể mount device vào container:

```yaml
camera-service:
  devices:
    - /dev/video0:/dev/video0
```

Hoặc chạy với `--privileged` flag.

## Network

Camera-Service sử dụng Docker network `adas-net` (bridge) để giao tiếp với RabbitMQ và các service khác.

```
┌──────────────────────────────────────────┐
│              adas-net (bridge)            │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ rabbitmq │  │ camera   │  │ driver │ │
│  │  :5672   │  │  :8005   │  │ :8001  │ │
│  └──────────┘  └──────────┘  └────────┘ │
│                                          │
└──────────────────────────────────────────┘
```

## Ports

| Port | Giao thức | Mục đích |
|------|-----------|----------|
| 8005 | HTTP | REST API |
| 5672 | AMQP | RabbitMQ (internal, không expose ra ngoài) |

## Volumes

> Chưa được triển khai trong phiên bản hiện tại.

Camera-Service hiện không sử dụng Docker volumes.

## Health Check

Camera-Service không có Docker healthcheck tích hợp. Dùng endpoint `/health` để kiểm tra:

```bash
curl http://localhost:8005/health
```

RabbitMQ container có healthcheck:

```yaml
healthcheck:
  test: ["CMD", "rabbitmq-diagnostics", "check_port_connectivity"]
  interval: 10s
  timeout: 5s
  retries: 5
```

## Khởi động toàn bộ hệ thống

### Cách chạy chuẩn (khuyến nghị)

**Camera-Service phải chạy native trên Windows** vì Docker Desktop không hỗ trợ webcam.
Các service còn lại (RabbitMQ, Driver, Seatbelt) chạy trong Docker.

```powershell
# Terminal 1: Khởi động RabbitMQ + Driver + Seatbelt trong Docker
# (Không khởi động camera-service trong Docker)
docker-compose up -d rabbitmq driver-service seatbelt-service

# Terminal 2: Camera-Service chạy native trên Windows
cd services/camera-service
pip install -r requirements.txt
$env:RABBITMQ_HOST = "localhost"
python main.py
```

**Tại sao cấu hình này hoạt động?**
- Camera native kết nối RabbitMQ qua `localhost:5672` (port đã được Docker expose).
- Driver và Seatbelt trong Docker kết nối RabbitMQ qua `rabbitmq:5672` (Docker DNS).
- Camera publish frame → RabbitMQ → Driver/Seatbelt consume → publish result → RabbitMQ → Camera consume.

**Lưu ý**: Không chạy `camera-service` trong Docker vì sẽ báo lỗi `Camera index=0 not available` và retry liên tục.

### Kiểm tra

```powershell
# Xem trạng thái container
docker-compose ps

# Health check
curl http://localhost:8005/health   # Camera (native)
curl http://localhost:8001/health   # Driver (Docker)
curl http://localhost:8007/health   # Seatbelt (Docker)

# RabbitMQ Management UI
# Mở browser: http://localhost:15672 (guest/guest)
```

## Dừng hệ thống

```powershell
# Terminal 2: Dừng camera (Ctrl+C)
# Terminal 1: Dừng Docker containers
docker-compose down
```

## Production Considerations

Những điểm cần lưu ý khi triển khai production:

1. **Credentials**: Thay đổi `guest/guest` thành credentials mạnh.
2. **TLS**: Bật TLS cho RabbitMQ connection.
3. **Resource limits**: Đặt CPU/memory limits cho container.
4. **Logging**: Cấu hình log rotation.
5. **Monitoring**: Thêm Prometheus metrics endpoint.
6. **Webcam permissions**: Đảm bảo user có quyền truy cập `/dev/video0`.
