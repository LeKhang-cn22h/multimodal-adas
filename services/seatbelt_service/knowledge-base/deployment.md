# Triển khai - Seatbelt-Service

## Docker

```bash
cd services/seatbelt_service
docker build -t adas-seatbelt:latest .
```

### Docker Compose

```yaml
seatbelt-service:
  build:
    context: ./services/seatbelt_service
  ports:
    - "8007:8007"
  environment:
    RABBITMQ_HOST: rabbitmq
    MODEL_PATH: best.pt
  depends_on:
    rabbitmq:
      condition: service_healthy
  networks:
    - adas-net
```

## Ports

| Port | Mục đích |
|------|----------|
| 8007 | REST API |

## Environment

| Biến | Mặc định                         |
|------|----------------------------------|
| `RABBITMQ_HOST` | `localhost` (Docker: `rabbitmq`) |
| `MODEL_PATH` | `best.pt`                        |
| `CONFIDENCE_THRESHOLD` | `0.3`                            |
| `WARNING_FRAMES` | `10`                             |
| `PORT` | `8007`                           |

## Khởi động

```bash
# Docker
docker-compose up -d seatbelt-service

# Native
cd services/seatbelt_service
pip install -r requirements.txt
set RABBITMQ_HOST=localhost
python main.py
```
