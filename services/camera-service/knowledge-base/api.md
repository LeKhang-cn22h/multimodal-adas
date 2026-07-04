# API Reference - Camera-Service

## REST API Endpoints

### GET /health

**Mô tả**: Kiểm tra trạng thái sức khỏe của dịch vụ.

**Response** (JSON):
```json
{
    "status": "healthy",
    "camera": true
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `status` | string | `"healthy"` - camera đang chạy; `"degraded"` - camera không hoạt động |
| `camera` | boolean | `true` nếu camera capture thread đang chạy |

**Status codes**:
- `200` - Thành công

---

### GET /frame

**Mô tả**: Trả về JPEG frame mới nhất từ camera.

**Response**: Raw JPEG bytes với `Content-Type: image/jpeg`.

**Status codes**:
- `200` - Frame JPEG
- `204` - Chưa có frame nào được capture

---

### GET /info

**Mô tả**: Trả về metadata của frame hiện tại.

**Response** (JSON):
```json
{
    "frame_id": 1543,
    "timestamp": 1691234567.890,
    "width": 640,
    "height": 480,
    "fps": 29.97
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `frame_id` | int | Số thứ tự frame (tăng dần từ 1) |
| `timestamp` | float | Unix timestamp của frame mới nhất |
| `width` | int | Độ rộng thực tế (pixels) |
| `height` | int | Độ cao thực tế (pixels) |
| `fps` | float | FPS camera hiện tại |

---

### GET /stats

**Mô tả**: Trả về thống kê runtime.

**Response** (JSON):
```json
{
    "uptime": 3600.5,
    "total_frames": 108000,
    "camera_fps": 30.01
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `uptime` | float | Thời gian hoạt động (giây) |
| `total_frames` | int | Tổng số frame đã capture |
| `camera_fps` | float | FPS trung bình |

---

## RabbitMQ Architecture

### Exchange

| Thuộc tính | Giá trị |
|------------|---------|
| Tên | `adas.exchange` |
| Loại | `topic` |
| Durable | `true` |
| Auto-delete | `false` |

### Queues (Camera-Service là Publisher)

| Queue | Routing Key | Durable | Mục đích |
|-------|-------------|---------|----------|
| `driver.frames` | `driver.frame` | true | Frame cho Driver-Service |
| `seatbelt.frames` | `seatbelt.frame` | true | Frame cho Seatbelt-Service |

### Queues (Camera-Service là Consumer)

| Queue | Routing Key | Durable | Mục đích |
|-------|-------------|---------|----------|
| `driver.results` | `driver.result` | true | Kết quả phát hiện buồn ngủ |
| `seatbelt.results` | `seatbelt.result` | true | Kết quả phát hiện dây an toàn |

### Message Formats

#### Frame Message

**Body**: Raw JPEG bytes (binary)
**Properties**:
- `delivery_mode`: 2 (persistent)
- `content_type`: `image/jpeg`
- `headers`:
  - `frame_id`: int → string
  - `timestamp`: float → string

#### Driver Result Message

**Body** (JSON):
```json
{
    "frame_id": 42,
    "timestamp": 1691234567.890,
    "sleepy": true,
    "confidence": 0.95
}
```

#### Seatbelt Result Message

**Body** (JSON):
```json
{
    "frame_id": 100,
    "timestamp": 1691234568.123,
    "seatbelt": true,
    "confidence": 0.88
}
```

### Binding Diagram

```
                     adas.exchange (topic)
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   driver.frame       seatbelt.frame      driver.result      seatbelt.result
        │                   │                   │                   │
        ▼                   ▼                   ▼                   ▼
  driver.frames       seatbelt.frames     driver.results     seatbelt.results
   [PUB: Camera]       [PUB: Camera]      [SUB: Camera]      [SUB: Camera]
   [SUB: Driver]       [SUB: Seatbelt]    [PUB: Driver]      [PUB: Seatbelt]
```
