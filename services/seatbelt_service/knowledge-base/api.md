# API Reference - Seatbelt-Service

## REST API

### GET /health
```json
{"status": "healthy", "model_loaded": true, "camera_reachable": true}
```

### GET /check
```json
{
    "seatbelt_detected": true,
    "no_seatbelt_streak": 0,
    "warning": false,
    "detections": [],
    "timestamp": 1691234567.890,
    "inference_time_ms": 0.0
}
```

### GET /stats
```json
{
    "uptime": 3600.5,
    "total_checks": 100,
    "seatbelt_ok_count": 85,
    "seatbelt_missing_count": 15,
    "avg_inference_ms": 250.5
}
```

## RabbitMQ

### Exchange
- `adas.exchange` (topic, durable)

### Consumer
| Queue | Routing Key | Ghi chú |
|-------|-------------|---------|
| `seatbelt.frames` | `seatbelt.frame` | Nhận JPEG từ Camera |

### Publisher
| Routing Key | Queue | Ghi chú |
|-------------|-------|---------|
| `seatbelt.result` | `seatbelt.results` | Gửi JSON cho Camera |

### Message Formats

**Frame Input**: Raw JPEG bytes + headers `{frame_id, timestamp}`

**Result Output** (JSON):
```json
{
    "frame_id": 100,
    "timestamp": 1691234568.123,
    "seatbelt": true,
    "confidence": 0.88
}
```
