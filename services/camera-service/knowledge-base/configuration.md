# Cấu hình - Camera-Service

## Tổng quan

Camera-Service sử dụng biến môi trường (environment variables) cho tất cả cấu hình. Không có file cấu hình YAML hay JSON. Cấu hình được load trong `app/core/config.py` thông qua class `Settings`.

## File .env

Vị trí: `D:\computer vision\multimodal-adas\.env` (file gốc của dự án).

### Biến môi trường đầy đủ

#### Camera Configuration

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `CAMERA_INDEX` | `0` | Chỉ số camera (0 = webcam mặc định, 1 = camera ngoài) |
| `JPEG_QUALITY` | `85` | Chất lượng nén JPEG (0-100). 85 cân bằng tốt giữa chất lượng và kích thước. |
| `FRAME_WIDTH` | `640` | Độ rộng frame mục tiêu. Camera sẽ cố gắng set resolution này. |
| `FRAME_HEIGHT` | `480` | Độ cao frame mục tiêu. |
| `DEFAULT_FPS` | `30` | FPS mặc định dùng cho hiển thị. Không ảnh hưởng capture FPS. |

#### RabbitMQ Configuration

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `RABBITMQ_HOST` | `localhost` | Hostname RabbitMQ. Trong Docker: `rabbitmq`. |
| `RABBITMQ_PORT` | `5672` | AMQP port. |
| `RABBITMQ_VHOST` | `/` | Virtual host. Mặc định `/` là đủ cho hầu hết use case. |
| `RABBITMQ_USER` | `guest` | Username. **Nên thay đổi trong production.** |
| `RABBITMQ_PASS` | `guest` | Password. **Nên thay đổi trong production.** |

#### Seatbelt Throttle

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `SEATBELT_FRAME_INTERVAL` | `600.0` | Khoảng cách (giây) giữa các frame gửi cho Seatbelt-Service. |

#### Service Configuration

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `PORT` | `8005` | HTTP port cho REST API. |
| `LOG_LEVEL` | `INFO` | Mức log: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `SERVICE_NAME` | `camera-service` | Tên service xuất hiện trong log. |

## Cách cấu hình

### Local Development (Windows)

```cmd
set CAMERA_INDEX=0
set RABBITMQ_HOST=localhost
set RABBITMQ_PORT=5672
set LOG_LEVEL=DEBUG
python main.py
```

### Docker Compose

```yaml
camera-service:
  environment:
    - RABBITMQ_HOST=rabbitmq
    - SEATBELT_FRAME_INTERVAL=300
```

### Production

```bash
export RABBITMQ_HOST=rabbitmq.production.internal
export RABBITMQ_USER=adas_user
export RABBITMQ_PASS=secure_password_here
export LOG_LEVEL=WARNING
```

## Cấu hình trong code

```python
# app/core/config.py
class Settings:
    CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))
    # ... các biến khác

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

- `Settings` được khởi tạo một lần và cache bằng `@lru_cache()`.
- Tất cả giá trị được đọc tại thời điểm import module (startup).
- Nếu cần thay đổi cấu hình, phải restart service.

## Docker Compose Environment

Biến môi trường trong `docker-compose.yml` cho camera-service:

```yaml
environment:
  PORT: 8005
  CAMERA_INDEX: ${CAMERA_INDEX:-0}        # Từ .env hoặc default
  JPEG_QUALITY: ${JPEG_QUALITY:-85}
  FRAME_WIDTH: ${FRAME_WIDTH:-640}
  FRAME_HEIGHT: ${FRAME_HEIGHT:-480}
  DEFAULT_FPS: ${DEFAULT_FPS:-30}
  LOG_LEVEL: ${LOG_LEVEL:-INFO}
  RABBITMQ_HOST: rabbitmq                  # Hardcoded vì là tên service trong compose
  RABBITMQ_PORT: 5672
  RABBITMQ_VHOST: /
  RABBITMQ_USER: guest
  RABBITMQ_PASS: guest
  SEATBELT_FRAME_INTERVAL: ${SEATBELT_FRAME_INTERVAL:-600}
```

- Các biến có `${VAR:-default}` sẽ lấy từ file `.env` nếu có, nếu không dùng default.
- `RABBITMQ_HOST=rabbitmq` được hardcode vì đây là tên service trong Docker Compose network.

## Xác thực cấu hình

> Chưa được triển khai trong phiên bản hiện tại.

Hiện tại không có validation khi khởi động. Các giá trị không hợp lệ (vd: `CAMERA_INDEX="abc"`) sẽ gây lỗi runtime.
