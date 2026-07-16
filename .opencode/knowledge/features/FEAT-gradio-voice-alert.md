# FEAT-gradio-voice-alert: Giao diện Gradio + Voice Alert

## Thuộc Requirement
[REQ-gradio-voice-alert](../requirements/REQ-gradio-voice-alert.md)

## Service
**driver-service** — thêm module mới, sửa `main.py` + `orchestrator.py`:
- `app/ui/gradio_app.py` — giao diện Gradio
- `app/services/voice_alert.py` — TTS + audio playback
- `app/messaging/orchestrator.py` — **sửa**: thêm `latest_result`, tích hợp `SeatbeltDetector`
- `app/main.py` — **sửa**: mount Gradio, init voice_alert, init seatbelt

## Mô tả chức năng

### 1. Gradio UI (`app/ui/gradio_app.py`)

Giao diện web real-time hiển thị:

| Thành phần | Mô tả |
|---|---|
| **Video feed** | Hiển thị webcam frame mới nhất (JPEG → numpy), cập nhật ~10 fps |
| **Fatigue level** | Text lớn + màu: Awake (xanh), Tired (vàng), Drowsy (cam), Dangerous (đỏ) |
| **Confidence bar** | Progress bar 0-100% |
| **Classification method** | "rule_based" hoặc "random_forest" |
| **Seatbelt status** | ON (xanh) / OFF (đỏ) — dữ liệu từ SeatbeltDetector trong orchestrator |
| **Cảnh báo cuối cùng** | Text hiển thị cảnh báo vừa phát (fatigue / seatbelt) |
| **Stats** | Tổng frame đã xử lý, uptime, FPS |

**Cơ chế cập nhật**: `gr.Blocks` + timer ~100ms, gọi orchestrator lấy
`latest_jpeg` + `latest_result`.

### 2. Voice Alert (`app/services/voice_alert.py`)

| Thành phần | Mô tả |
|---|---|
| **Input** | Loại cảnh báo: `"fatigue"` hoặc `"seatbelt"` |
| **Triggers** | Fatigue: level = Drowsy/Dangerous. Seatbelt: has_seatbelt = False |
| **Cooldown** | Riêng cho từng loại (mặc định 10s), configurable |
| **TTS Model** | MMS-TTS-VIE (`facebook/mms-tts-vie`) từ HuggingFace |
| **Audio output** | Phát qua loa máy tính dùng `sounddevice` |
| **Nội dung** | Fatigue: "Cảnh báo! Tài xế đang buồn ngủ, hãy dừng xe nghỉ ngơi!" |
| | Seatbelt: "Cảnh báo! Vui lòng thắt dây an toàn!" |

### 3. SeatbeltDetector trong Orchestrator

Thêm `SeatbeltDetector` vào orchestrator worker loop, chạy song song với
`FatigueDetector`:

```python
# orchestrator._worker_loop()
fatigue_result = self._detector.process(jpeg_bytes, ...)
seatbelt_result = self._seatbelt_detector.detect(frame)

combined = {
    **fatigue_result,
    "has_seatbelt": seatbelt_result["has_seatbelt"],
    "seatbelt_confidence": seatbelt_result.get("seatbelt_confidence"),
}
self._latest_result = combined
self._publisher.publish(combined)
```

## Acceptance Criteria

| # | Tiêu chí |
|---|---------|
| AC-1 | Mở `http://localhost:8001/ui` thấy giao diện Gradio với webcam feed |
| AC-2 | Fatigue level hiển thị đúng màu theo mức độ |
| AC-3 | Confidence bar cập nhật theo từng frame |
| AC-4 | Seatbelt status hiển thị ON/OFF đúng màu |
| AC-5 | Khi fatigue = Drowsy/Dangerous → loa phát "Cảnh báo! Tài xế đang buồn ngủ..." |
| AC-6 | Khi seatbelt = OFF → loa phát "Cảnh báo! Vui lòng thắt dây an toàn!" |
| AC-7 | Mỗi loại cảnh báo có cooldown riêng, không phát lại trong 10s |
| AC-8 | Model TTS load 1 lần trong lifespan, không reload |
| AC-9 | API `/health`, `/stats`, `/frame` vẫn hoạt động bình thường |
| AC-10 | UI hoạt động ngay cả khi RabbitMQ không kết nối |

## Độ ưu tiên
**P1** — giao diện người dùng là cần thiết để demo và kiểm thử toàn bộ
pipeline, nhưng không block các tính năng AI core.

## Phụ thuộc
- `CameraCaptureService` trong orchestrator phải hoạt động (cung cấp
  `latest_jpeg`). Hiện đang pending implement — nếu chưa có, FEAT này
  sẽ implement cùng lúc.
- `SeatbeltDetector` đã có sẵn trong `app/services/seatbelt_detector.py`.
