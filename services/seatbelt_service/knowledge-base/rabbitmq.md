# RabbitMQ Design - Seatbelt-Service

## Vai trò trong hệ thống

Seatbelt-Service là **Consumer** của `seatbelt.frames` và **Publisher** của `seatbelt.results`.

## Exchange và Queue

```
adas.exchange (topic)
    │
    ├── seatbelt.frame  → seatbelt.frames  [SUB: Seatbelt-Service]
    └── seatbelt.result → seatbelt.results [PUB: Seatbelt-Service]
```

## Consumer Config

| Thuộc tính | Giá trị | Lý do |
|------------|---------|-------|
| prefetch_count | 1 | Tránh quá tải YOLO |
| auto_ack | true | Frame cũ không cần retry |
| durable | true | Tồn tại sau restart |

## Publisher Config

| Thuộc tính | Giá trị |
|------------|---------|
| delivery_mode | 2 (persistent) |
| content_type | application/json |

## Message Flow

```
Camera-Service → basic_publish("adas.exchange", "seatbelt.frame", JPEG)
    → seatbelt.frames
    → Seatbelt FrameConsumer: _on_frame_message()
    → SeatbeltDetector.process() → YOLO
    → ResultPublisher.publish(result)
    → basic_publish("adas.exchange", "seatbelt.result", JSON)
    → seatbelt.results
    → Camera ResultConsumer
```

## Reconnect Strategy

Giống Camera-Service: Exponential backoff (1s → 2s → 4s → ... → 30s).

## Khả năng mở rộng

- Nhiều instance Seatbelt-Service → RabbitMQ round-robin trên queue `seatbelt.frames`.
- Mỗi instance có prefetch_count=1 → xử lý tuần tự.
