# Driver Monitoring Service — Tích hợp

Service chạy tại `http://localhost:8001`, cung cấp 2 cách tích hợp:

---

## Cách 1: Nhúng giao diện (iframe)

Nhúng toàn bộ UI vào app của bạn:

```html
<iframe src="http://localhost:8001/ui/?return_url=YOUR_APP_URL"
        width="100%" height="700" style="border:none;">
</iframe>
```

- `return_url` (tùy chọn): nút **← Quay lại** sẽ xuất hiện, bấm vào redirect về app của bạn
- Không có `return_url` → UI đầy đủ, không nút quay lại

---

## Cách 2: Gọi REST API (tự build frontend)

### Bắt đầu monitoring

```bash
# Webcam
curl -X POST http://localhost:8001/driver/monitor/start \
  -H "Content-Type: application/json" \
  -d '{"source": "webcam"}'

# Video file
curl -X POST http://localhost:8001/driver/monitor/start \
  -H "Content-Type: application/json" \
  -d '{"source": "/path/to/video.mp4"}'
```

**Response:**
```json
{
  "status": "started",
  "source": "webcam",
  "video_feed_url": "/video_feed"
}
```

### Hiển thị video (MJPEG stream)

```html
<img src="http://localhost:8001/video_feed">
```

### Poll trạng thái

```bash
curl http://localhost:8001/driver/monitor/status
```

**Response:**
```json
{
  "active": true,
  "drowsiness": "NORMAL",
  "eye": "OPEN",
  "eye_confidence": 0.95,
  "mouth": "NO_YAWN",
  "seatbelt": "ON",
  "frame": 142,
  "fps": 28.5,
  "elapsed": 5.0
}
```

| Field | Ý nghĩa |
|-------|---------|
| `drowsiness` | `NORMAL` / `DROWSY` / `NO_FACE` |
| `eye` | `OPEN` / `CLOSED` |
| `mouth` | `YAWN` / `NO_YAWN` |
| `seatbelt` | `ON` / `OFF` |

### Dừng monitoring

```bash
curl -X POST http://localhost:8001/driver/monitor/stop
```

---

## Ví dụ: Trang HTML tối giản

```html
<!DOCTYPE html>
<html>
<head><title>Driver Monitor</title></head>
<body>
  <h1>Driver Monitoring</h1>

  <button onclick="start('webcam')">Webcam</button>
  <button onclick="stop()">Dừng</button>

  <div id="status"></div>
  <img id="feed" src="">

  <script>
    const BASE = 'http://localhost:8001';

    async function start(source) {
      const res = await fetch(BASE + '/driver/monitor/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({source})
      });
      const data = await res.json();
      document.getElementById('feed').src = BASE + data.video_feed_url;
      pollStatus();
    }

    async function stop() {
      await fetch(BASE + '/driver/monitor/stop', {method: 'POST'});
      document.getElementById('feed').src = '';
    }

    async function pollStatus() {
      const res = await fetch(BASE + '/driver/monitor/status');
      const s = await res.json();
      document.getElementById('status').innerText =
        `Eye: ${s.eye} | Drowsiness: ${s.drowsiness} | Seatbelt: ${s.seatbelt}`;
      if (s.active) setTimeout(pollStatus, 500);
    }
  </script>
</body>
</html>
```

---

## Tổng quan API

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/driver/monitor/start` | POST | Bắt đầu monitoring |
| `/driver/monitor/stop` | POST | Dừng monitoring |
| `/driver/monitor/status` | GET | Trạng thái real-time |
| `/video_feed` | GET | MJPEG stream (nhúng `<img>`) |
| `/ui` | GET | Giao diện Gradio đầy đủ |
| `/health` | GET | Health check |
