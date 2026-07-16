# TS-gradio-voice-alert: Gradio UI + Voice Alert tích hợp driver-service

## Thuộc Feature
[FEAT-gradio-voice-alert](../features/FEAT-gradio-voice-alert.md)

## Kiến trúc

### File tạo mới / sửa

| File | Hành động | Lớp (Layer) |
|------|-----------|-------------|
| `app/ui/__init__.py` | Tạo mới | UI layer |
| `app/ui/gradio_app.py` | Tạo mới | UI layer — Gradio Blocks |
| `app/services/voice_alert.py` | Tạo mới | Services layer — TTS + playback |
| `app/messaging/orchestrator.py` | **Sửa** | Thêm `latest_result`, tích hợp `SeatbeltDetector` |
| `app/core/config.py` | **Sửa** | Thêm `VOICE_COOLDOWN_SECONDS`, `SEATBELT_COOLDOWN_SECONDS` |
| `app/main.py` | **Sửa** | Mount Gradio, init VoiceAlertService |

### Sơ đồ luồng dữ liệu

```
┌──────────────────────────────────────────────────────────────┐
│  driver-service (single process)                             │
│                                                              │
│  ┌──────────┐    ┌──────────────────────┐    ┌────────────┐  │
│  │ Webcam   │───▶│    Orchestrator       │───▶│ RabbitMQ   │  │
│  │ (thread) │    │                       │    │ (external) │  │
│  └──────────┘    │  FatigueDetector      │    └────────────┘  │
│                  │  SeatbeltDetector (NEW)                   │
│                  │                       │                   │
│                  │ .latest_jpeg          │                   │
│                  │ .latest_result        │                   │
│                  │   ├── fatigue_level   │                   │
│                  │   ├── confidence      │                   │
│                  │   ├── has_seatbelt    │                   │
│                  │   └── ...             │                   │
│                  └──────┬────────────────┘                   │
│                         │                                   │
│              ┌──────────┴──────────┐                        │
│              ▼                     ▼                        │
│  ┌─────────────────────┐  ┌──────────────────────┐          │
│  │ Gradio UI (/ui)     │  │ VoiceAlertService     │          │
│  │ - webcam feed       │  │ - MMS-TTS-VIE         │          │
│  │ - fatigue level     │  │ - sounddevice         │          │
│  │ - confidence bar    │  │ - cooldown fatigue 10s │          │
│  │ - seatbelt ON/OFF   │  │ - cooldown seatbelt 10s│          │
│  │ - last alert text   │  │ - 2 câu cảnh báo      │          │
│  │ - stats (fps, ...)  │  └──────────────────────┘          │
│  └─────────────────────┘                                    │
│                                                              │
│  ┌─────────────────────┐                                    │
│  │ FastAPI (/health,    │                                   │
│  │  /stats, /frame)     │                                   │
│  └─────────────────────┘                                    │
└──────────────────────────────────────────────────────────────┘
```

### Tương tác giữa các layer

```
api/ ──▶ (không gọi ui/ — Gradio dùng orchestrator trực tiếp)
ui/  ──▶ messaging/orchestrator (get_orchestrator singleton)
     ──▶ services/voice_alert (gọi khi fatigue ≥ Drowsy hoặc seatbelt OFF)
```

**Tuân thủ Layered Architecture**: `ui/` là layer mới, ngang hàng với
`api/`. Cả 2 đều gọi `services/` và `orchestrator` nhưng không gọi nhau.

### Chi tiết từng file

#### 1. `app/messaging/orchestrator.py` — sửa: +SeatbeltDetector +latest_result

```python
class MessagingOrchestrator:
    def __init__(self):
        ...
        # ── Seatbelt detector (NEW) ────────────────────────────
        self._seatbelt_detector = SeatbeltDetector(
            model_path=settings.SEATBELT_MODEL_PATH,
        )

        # ── Latest result cache (NEW) ───────────────────────────
        self._latest_result: dict | None = None

    @property
    def latest_result(self) -> dict | None:
        return self._latest_result

    def _worker_loop(self):
        ...
        # Fatigue detection
        jpeg_bytes = self._frame_queue.get(timeout=0.5)
        frame = self._detector._decode_jpeg(jpeg_bytes)

        fatigue_result = self._detector.process(jpeg_bytes, frame_id, timestamp)

        # Seatbelt detection (NEW — chạy song song)
        seatbelt_result = self._seatbelt_detector.detect(frame) if frame is not None else {"has_seatbelt": False}

        # Combine results
        combined = {
            **fatigue_result,
            "has_seatbelt": seatbelt_result["has_seatbelt"],
            "seatbelt_confidence": seatbelt_result.get("seatbelt_confidence"),
        }
        self._latest_result = combined
        self._publisher.publish(combined)
        frame_id += 1
```


#### 2. `app/services/voice_alert.py` — tạo mới

```python
class VoiceAlertService:
    """Text-to-speech + audio playback với cooldown riêng cho từng loại."""

    # ── Các câu cảnh báo ────────────────────────────────────────
    MSG_FATIGUE = "Cảnh báo! Tài xế đang buồn ngủ, hãy dừng xe nghỉ ngơi!"
    MSG_SEATBELT = "Cảnh báo! Vui lòng thắt dây an toàn!"

    def __init__(self, model_name: str, cooldown_seconds: float, device: str):
        self._model = None          # VitsModel
        self._tokenizer = None      # VitsTokenizer
        self._sample_rate = None
        self._cooldown = cooldown_seconds
        self._last_alert_times: dict[str, float] = {}  # "fatigue" | "seatbelt"
        self._device = device

    def load_model(self): ...
    def alert_fatigue(self, level: str) -> bool:
        """Phát cảnh báo fatigue nếu level >= Drowsy và qua cooldown."""
    def alert_seatbelt(self, has_seatbelt: bool) -> bool:
        """Phát cảnh báo seatbelt nếu không thắt và qua cooldown."""
    def _speak(self, text: str) -> bool:
        """TTS + playback, trả về True nếu phát thành công."""
    def _check_cooldown(self, alert_type: str) -> bool: ...
    def close(self): ...
```

**Logic cảnh báo trong VoiceAlertService:**

```
Input: latest_result dict từ orchestrator
  │
  ├── fatigue_level in ["Drowsy", "Dangerous"] ?
  │   ├── YES → _check_cooldown("fatigue")?
  │   │   ├── YES → TTS(MSG_FATIGUE) → playback → update time
  │   │   └── NO  → skip
  │   └── NO → skip
  │
  ├── has_seatbelt == False?
  │   ├── YES → _check_cooldown("seatbelt")?
  │   │   ├── YES → TTS(MSG_SEATBELT) → playback → update time
  │   │   └── NO  → skip
  │   └── NO → skip
```

#### 3. `app/ui/gradio_app.py` — tạo mới

```python
def build_ui(orchestrator, voice_alert) -> gr.Blocks:
    """Xây dựng giao diện Gradio."""

    with gr.Blocks(title="Driver Monitoring") as demo:
        # ── Header ──
        gr.Markdown("# 🚗 Driver Monitoring System")

        with gr.Row():
            # Cột trái: Webcam feed
            with gr.Column(scale=2):
                video = gr.Image(label="Webcam", every=0.1)  # 10 fps

            # Cột phải: Trạng thái
            with gr.Column(scale=1):
                fatigue_label = gr.Label(label="Fatigue Level")
                confidence_bar = gr.Slider(
                    label="Confidence", minimum=0, maximum=100
                )
                method_text = gr.Textbox(label="Classifier")
                seatbelt_text = gr.Textbox(label="Seatbelt")
                last_alert_text = gr.Textbox(label="Last Alert")

        # ── Stats ──
        with gr.Row():
            fps_text = gr.Textbox(label="FPS")
            frames_text = gr.Textbox(label="Total Frames")
            uptime_text = gr.Textbox(label="Uptime")

        # ── Timer update ──
        def update_ui():
            """Gọi bởi timer ~100ms, đọc orchestrator, trả về dict."""
            ...

        demo.load(update_ui, outputs=[...], every=0.1)

    return demo
```

#### 4. `app/main.py` — sửa

```python
from app.ui.gradio_app import build_ui
from app.services.voice_alert import VoiceAlertService
import gradio as gr

@asynccontextmanager
async def lifespan(app: FastAPI):
    ...
    orchestrator.start()

    # Init voice alert
    voice_alert = VoiceAlertService(
        model_name="facebook/mms-tts-vie",
        cooldown_seconds=settings.VOICE_COOLDOWN_SECONDS,
        device="cpu",
    )
    voice_alert.load_model()
    app.state.voice_alert = voice_alert

    yield
    ...
    voice_alert.close()

# Mount Gradio
gradio_app = build_ui(get_orchestrator(), ...)  # voice_alert lấy từ app.state
app = gr.mount_gradio_app(app, gradio_app, path="/ui")
```

## Logic + AI

### Model: MMS-TTS-VIE (Facebook/Meta)

| Thuộc tính | Giá trị |
|---|---|
| **Tên model** | `facebook/mms-tts-vie` |
| **Loại** | VITS (Variational Inference with adversarial learning for end-to-end TTS) |
| **Ngôn ngữ** | Tiếng Việt |
| **Input** | Text string (VD: "Cảnh báo! Tài xế đang buồn ngủ...") |
| **Output** | `numpy.ndarray`, shape `(num_samples,)`, dtype `float32`, sample_rate 16000 |
| **Thư viện** | `transformers` (VitsModel + VitsTokenizer) |
| **Độ phức tạp** | ~1-3 giây cho 1 câu ngắn (CPU), model ~300MB |
| **License** | CC-BY-NC 4.0 (nghiên cứu phi thương mại) |

**Pipeline TTS:**
```
text → VitsTokenizer → input_ids → VitsModel.generate() → waveform (float32)
     → sounddevice.play(waveform, samplerate=16000)
```

### Voice Alert Service — logic cảnh báo

```
Input: fatigue_level (str), timestamp (float)
  │
  ├── fatigue_level in ["Drowsy", "Dangerous"] ?
  │   ├── YES:
  │   │   ├── _should_alert()?  (now - last_alert >= cooldown)
  │   │   │   ├── YES → TTS → playback → update last_alert_time → return True
  │   │   │   └── NO  → skip → return False
  │   └── NO → skip → return False
```

### Ngưỡng cảnh báo

| Tham số | Giá trị mặc định | Env var |
|---------|-----------------|---------|
| Cooldown chung | 10 giây | `VOICE_COOLDOWN_SECONDS` |
| Trigger fatigue | `["Drowsy", "Dangerous"]` | hardcode |
| Trigger seatbelt | `has_seatbelt == False` | hardcode |
| Sample rate | 16000 Hz | (TTS model output) |
| Nội dung fatigue | "Cảnh báo! Tài xế đang buồn ngủ, hãy dừng xe nghỉ ngơi!" | hardcode |
| Nội dung seatbelt | "Cảnh báo! Vui lòng thắt dây an toàn!" | hardcode |

## API Contract

### Không thêm API mới — chỉ mount Gradio UI

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/ui` | GET | Gradio web UI (do `gr.mount_gradio_app` xử lý) |
| `/health` | GET | **Giữ nguyên**, không đổi |
| `/stats` | GET | **Giữ nguyên**, không đổi |
| `/frame` | GET | **Giữ nguyên**, không đổi |

## Cấu trúc thư mục kết quả

```
app/
├── api/                # không đổi
├── core/
│   └── config.py       # sửa: thêm VOICE_COOLDOWN_SECONDS
├── messaging/
│   └── orchestrator.py # sửa: +SeatbeltDetector, +latest_result
├── services/
│   ├── seatbelt_detector.py  # đã có sẵn
│   └── voice_alert.py        # TẠO MỚI
├── ui/                 # TẠO MỚI (layer)
│   ├── __init__.py
│   └── gradio_app.py
├── main.py             # sửa: mount Gradio, init voice_alert
└── ...
```

## Rủi ro & câu hỏi mở

1. **Gradio + FastAPI same process**: `gr.mount_gradio_app` có thể gây
   xung đột port nếu FastAPI và Gradio đều muốn bind. Giải pháp: dùng
   `mount_gradio_app` (Gradio 4.x) — nó mount Gradio như 1 route của
   FastAPI, không mở port riêng.

2. **MMS-TTS model size**: ~300MB, tải lần đầu từ HuggingFace có thể
   mất vài phút. Cần cache local ở `~/.cache/huggingface/`.

3. **CameraCaptureService chưa implement**: Orchestrator import
   `CameraCaptureService` nhưng file chưa tồn tại. TS này giả định
   `camera_service.latest_jpeg` sẽ có khi camera chạy. Nếu chưa có,
   UI sẽ hiển thị "No camera" placeholder.

4. **TTS inference latency**: TTS trên CPU mất 1-3 giây — chạy trong
   thread riêng (`threading.Thread`) để không block UI update.

5. **`gr.Image` với `every=`**: Gradio `every=` parameter yêu cầu
   function trả về cùng 1 component type. Dùng `gr.Image` với numpy array
   BGR → RGB để hiển thị webcam feed.

6. **CPU usage**: TTS inference trên CPU có thể mất 1-3 giây — nên chạy
   trong thread riêng để không block UI.

## Ảnh hưởng tới service khác
- **Không** ảnh hưởng service khác. Chỉ thay đổi trong driver-service.

## Trạng thái xác nhận
`[x] Đã xác nhận bởi người dùng ngày 2026-07-16` — đã implement.
