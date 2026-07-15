# TS-merged-monitoring: Gộp Seatbelt + Video Input vào Driver-Service

## Thuộc Feature
`.opencode/knowledge/features/FEAT-merged-monitoring.md`

---

## 1. Kiến trúc tổng thể

### 1.1 Data Flow (sau khi gộp)

```
┌─────────────────────────────────────────────────────────────────┐
│                     driver-service (modified)                    │
│                                                                  │
│  ┌──────────────────────┐    ┌──────────────────────────────┐   │
│  │  Frame Source Thread │    │       API (main thread)       │   │
│  │                      │    │  GET /health, /stats, /frame  │   │
│  │  CameraCaptureService│    │  POST /video/pause            │   │
│  │        XOR           │    │  POST /video/resume           │   │
│  │  VideoFileReader     │    └──────────────────────────────┘   │
│  │                      │                                       │
│  │  read frame → encode │                                       │
│  │  JPEG → queue.Queue  │                                       │
│  └──────────┬───────────┘                                       │
│             │ jpeg_bytes                                        │
│             ▼                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              AI Worker Thread (dual pipeline)             │  │
│  │                                                          │  │
│  │  jpeg_bytes → cv2.imdecode → BGR frame                   │  │
│  │       │                                                  │  │
│  │       ├── FatigueDetector.process(jpeg_bytes, ...)       │  │
│  │       │     ├── FaceLandmarkerService.detect()           │  │
│  │       │     ├── FeatureService.extract() → 40 features   │  │
│  │       │     └── IClassifier.classify()                   │  │
│  │       │                                                  │  │
│  │       ├── SeatbeltDetector.process(jpeg_bytes, ...)      │  │
│  │       │     └── YOLO model(frame, conf=0.3)              │  │
│  │       │                                                  │  │
│  │       ├── ResultPublisher.publish(driver.result)         │  │
│  │       ├── SeatbeltPublisher.publish(seatbelt.result)     │  │
│  │       │                                                  │  │
│  │       └── display_queue.put((bgr_frame, fat_res, sb_res))│  │
│  └──────────┬───────────────────────────────────────────────┘  │
│             │ (bgr_frame, fatigue_result, seatbelt_result)      │
│             ▼                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          Display Thread (overlay + cv2.imshow)           │  │
│  │                                                          │  │
│  │  OverlayRenderer.render(bgr_frame, fat_res, sb_res)      │  │
│  │       ├── draw_yolo_boxes() — bounding box + label       │  │
│  │       ├── draw_drowsiness_text() — fatigue info          │  │
│  │       ├── draw_status_bar() — top bar summary            │  │
│  │       └── cv2.imshow("ADAS Monitor", rendered_frame)     │  │
│  │                                                          │  │
│  │  Keyboard: 'q'=quit, 'p'=pause/resume                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  (optional) ── RabbitMQ ──► driver.result                        │
│                         ──► seatbelt.result                      │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Layered Architecture Mapping

Tuân thủ chặt chẽ `.opencode/knowledge/architecture.md`:

| Layer | File | Trách nhiệm |
|---|---|---|
| **api/** | `api/fatigue.py` | SỬA: thêm `/video/pause`, `/video/resume`; cập nhật `/health` và `/stats` |
| **services/** | `services/seatbelt_detector.py` | **MỚI**: copy từ seatbelt_service, YOLO seatbelt inference |
| **services/** | `services/video_file_reader.py` | **MỚI**: thay thế webcam bằng video file |
| **services/** | `services/overlay_renderer.py` | **MỚI**: vẽ overlay + hiển thị OpenCV |
| **services/** | `services/fatigue_detector.py` | **GIỮ NGUYÊN**: không sửa |
| **services/** | `services/mediapipe_service.py` | **GIỮ NGUYÊN** |
| **services/** | `services/feature_service.py` | **GIỮ NGUYÊN** |
| **services/** | `services/feature_engineering.py` | **GIỮ NGUYÊN** |
| **services/** | `services/camera_capture_service.py` | **GIỮ NGUYÊN** |
| **services/** | `services/rf_classifier.py` | **GIỮ NGUYÊN** |
| **services/** | `services/rule_based_classifier.py` | **GIỮ NGUYÊN** |
| **services/** | `services/classifier_interface.py` | **GIỮ NGUYÊN** |
| **messaging/** | `messaging/orchestrator.py` | **SỬA**: thêm seatbelt, video mode, display thread |
| **messaging/** | `messaging/publisher.py` | SỬA nhẹ: thêm seatbelt routing key |
| **messaging/** | `messaging/connection.py` | **GIỮ NGUYÊN** |
| **core/** | `core/config.py` | SỬA: thêm env vars cho video + seatbelt |
| **utils/** | `utils/` (ear, mar, headpose, logger) | **GIỮ NGUYÊN** — pure functions |

---

## 2. Chi tiết từng file

### 2.1 File MỚI: `app/services/seatbelt_detector.py`

**Nguồn**: Copy 90% từ `seatbelt_service/app/services/seatbelt_detector.py`.

**Thay đổi so với bản gốc**:
- Import `get_settings` từ `app.core.config` của driver-service (thay vì
  seatbelt_service).
- Import `get_logger` từ `app.utils.logger` của driver-service.
- Đọc config key mới: `SEATBELT_MODEL_PATH`, `SEATBELT_CONFIDENCE_THRESHOLD`,
  `SEATBELT_WARNING_FRAMES` (thay vì `MODEL_PATH`, `CONFIDENCE_THRESHOLD`,
  `WARNING_FRAMES` của seatbelt_service).
- **Giữ nguyên** toàn bộ logic `load_model()`, `process()`, `_decode_jpeg()`,
  `_run_inference()`, `_update_stats()`, `_build_result()`.

**Class `SeatbeltDetector`**:
```
Input:  jpeg_bytes: bytes, frame_id: int, frame_timestamp: float
Output: dict {frame_id, timestamp, seatbelt: bool, confidence: float,
              detections: [{class_name, class_id, confidence, bbox}]}
```

**Model**: `best_1.pt` (YOLO, 7 classes, ~6.25 MB) — copy vào thư mục gốc
driver-service.

**Classes**:
| ID | Class | Màu overlay (BGR) |
|----|-------|-------------------|
| 0 | cell phone | (255, 165, 0) |
| 1 | drinking | (0, 165, 255) |
| 2 | eyeglass | (255, 255, 0) |
| 3 | hands off | (0, 0, 255) |
| 4 | hands on | (0, 255, 255) |
| 5 | mask | (255, 0, 255) |
| 6 | **seatbelt** | **(0, 255, 0)** |

**Ngưỡng**: `SEATBELT_CONFIDENCE_THRESHOLD=0.3` (mặc định, ghi đè qua env var).
**Warning**: `SEATBELT_WARNING_FRAMES=10` frame liên tiếp không có seatbelt → WARNING.

**Độ phức tạp**: YOLO inference ~20-50ms/frame trên GPU, ~100-300ms/frame trên CPU.

---

### 2.2 File MỚI: `app/services/video_file_reader.py`

**Class `VideoFileReader`** — thay thế `CameraCaptureService` khi `VIDEO_PATH` được set.

Thiết kế **cùng interface** với `CameraCaptureService` để orchestrator có thể
swap transparently:
- `__init__(frame_queue: queue.Queue)` — nhận queue, đọc config từ `get_settings()`.
- `start()` — mở video, launch capture thread.
- `stop()` — dừng thread, release video.
- `latest_jpeg`, `fps`, `is_running`, `dropped_frames` — thread-safe properties.
- `pause()`, `resume()`, `is_paused` — điều khiển pause/resume.
- `total_frames`, `current_frame_idx` — thông tin tiến độ video.

**Capture loop** (background thread `video-capture`):
```
while not stopped:
    if not paused:
        ret, frame = cap.read()
        if not ret:
            if loop: cap.set(cv2.CAP_PROP_POS_FRAMES, 0); continue
            else: break
        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
        encode JPEG → push to queue (put_nowait, drop if full)
        update latest_jpeg, frame_idx under lock
        sleep to match video FPS (tránh đọc quá nhanh)
    else:
        sleep(0.1)
```

**Config keys mới trong `Settings`**:

| Env var | Default | Mô tả |
|---|---|---|
| `VIDEO_PATH` | `""` | Đường dẫn video file. Nếu rỗng → dùng webcam. |
| `VIDEO_LOOP` | `false` | Loop video khi hết. |
| `VIDEO_START_FRAME` | `0` | Frame bắt đầu đọc. |

---

### 2.3 File MỚI: `app/services/overlay_renderer.py`

**Class `OverlayRenderer`** — pure rendering + display, không có AI logic.

Chạy trong **display thread** riêng (tên `display`), nhận frame từ `display_queue`
(`queue.Queue(maxsize=2)`).

**Input queue item**: `(bgr_frame: np.ndarray, fatigue_result: dict, seatbelt_result: dict)`

**Phương thức public**:
- `start()` — launch display thread.
- `stop()` — dừng thread, đóng cửa sổ OpenCV.
- `is_running` — thread-safe property.

**Display loop**:
```
while not stopped:
    try:
        bgr_frame, fat, sb = display_queue.get(timeout=0.5)
    except queue.Empty:
        continue

    rendered = self._render(bgr_frame, fat, sb)
    cv2.imshow("ADAS Monitor", rendered)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        signal orchestrator to shutdown
    elif key == ord('p'):
        toggle pause via callback
```

**`_render()` method** — pure function, dễ unit test:
```
def _render(frame, fatigue, seatbelt) -> np.ndarray:
    # 1. Vẽ YOLO bounding boxes (từ seatbelt["detections"])
    for det in seatbelt["detections"]:
        x1,y1,x2,y2 = det["bbox"]
        cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
        put_text_with_bg(frame, f"{label} {conf:.2f}", (x1,y1-5), color)

    # 2. Vẽ drowsiness text (từ fatigue)
    #    Góc trên-trái:
    #    "Fatigue: {level} ({score})"
    #    "EAR: {ear:.3f}  PERCLOS: {perclos:.1f}%  MAR: {mar:.3f}"
    #    "Yaw: {yaw:.1f}  Pitch: {pitch:.1f}  Roll: {roll:.1f}"

    # 3. Vẽ status bar (top edge)
    fat_color = GREEN if level=="Awake" else YELLOW if "Tired" else ORANGE if "Drowsy" else RED
    sb_color = GREEN if seatbelt["seatbelt"] else RED
    draw_status_bar(frame, f"FATIGUE: {level} | SEATBELT: {'OK' if sb else 'WARNING'}",
                    fat_color, sb_color)

    # 4. Vẽ frame counter + FPS (góc dưới-phải)

    return frame
```

**Màu sắc overlay**:
| Fatigue Level | Màu (BGR) |
|---|---|
| Awake | (0, 255, 0) — green |
| Tired | (0, 255, 255) — yellow |
| Drowsy | (0, 165, 255) — orange |
| Dangerous | (0, 0, 255) — red |
| Unknown | (128, 128, 128) — gray |

**Config key**: `ENABLE_DISPLAY=true/false` (mặc định `true`).

---

### 2.4 File SỬA: `app/messaging/orchestrator.py`

Đây là file thay đổi chính. Giữ nguyên cấu trúc hiện có, thêm các thành phần mới.

**Constructor — thêm**:
```python
# ── Frame source: video file XOR webcam ────────────────────────
if settings.VIDEO_PATH:
    self._video_reader = VideoFileReader(frame_queue=self._frame_queue)
    self._camera_service = None  # không dùng webcam
    self._frame_source_type = "video"
else:
    self._camera_service = CameraCaptureService(frame_queue=self._frame_queue)
    self._video_reader = None
    self._frame_source_type = "webcam"

# ── Seatbelt detector (YOLO) ────────────────────────────────────
self._seatbelt_detector = SeatbeltDetector()

# ── Display queue + overlay renderer ────────────────────────────
self._display_queue = queue.Queue(maxsize=2)
self._overlay_renderer = OverlayRenderer(
    display_queue=self._display_queue,
    on_quit_callback=self.stop,
    on_pause_callback=self._toggle_pause,
)

# ── Seatbelt result publisher (thêm channel riêng) ─────────────
self._seatbelt_publisher = ResultPublisher(self._connection_manager)
self._seatbelt_publisher.ROUTING_KEY = "seatbelt.result"
```

**`start()` — thêm**:
```python
# 1.5. Load YOLO model (sau MediaPipe)
if settings.VIDEO_PATH:
    self._seatbelt_detector.load_model()

# 2.5. Start seatbelt publisher
self._seatbelt_publisher.start()

# 4.5. Start display thread (nếu ENABLE_DISPLAY)
if settings.ENABLE_DISPLAY:
    self._overlay_renderer.start()

# 5. Start frame source (video hoặc webcam)
if self._frame_source_type == "video":
    self._video_reader.start()
else:
    self._camera_service.start()
```

**`stop()` — thêm**:
```python
# Stop display thread trước
self._overlay_renderer.stop()

# Stop frame source
if self._video_reader:
    self._video_reader.stop()
else:
    self._camera_service.stop()

# Stop seatbelt publisher
self._seatbelt_publisher.stop()

# Release YOLO model
del self._seatbelt_detector
```

**`_worker_loop()` — sửa nội dung**:
```python
def _worker_loop(self) -> None:
    frame_id = 0
    while not self._worker_stop_event.is_set():
        try:
            jpeg_bytes = self._frame_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        timestamp = time.time()

        # ── Decode JPEG once for overlay ──────────────────────
        bgr_frame = self._decode_for_display(jpeg_bytes)

        # ── Pipeline 1: Drowsiness (KHÔNG SỬA logic gốc) ──────
        fatigue_result = self._detector.process(jpeg_bytes, frame_id, timestamp)

        # ── Pipeline 2: Seatbelt (KHÔNG SỬA logic gốc) ────────
        seatbelt_result = self._seatbelt_detector.process(jpeg_bytes, frame_id, timestamp)

        # ── Publish results (optional, graceful degradation) ──
        self._publisher.publish(fatigue_result)
        self._seatbelt_publisher.publish(seatbelt_result)

        # ── Push to display queue ────────────────────────────
        if bgr_frame is not None:
            try:
                self._display_queue.put_nowait((bgr_frame, fatigue_result, seatbelt_result))
            except queue.Full:
                pass  # drop frame for display if renderer is slow

        frame_id += 1
```

**Decoder riêng cho display** (để tránh sửa FatigueDetector/SeatbeltDetector):
```python
@staticmethod
def _decode_for_display(jpeg_bytes: bytes) -> Optional[np.ndarray]:
    import cv2, numpy as np
    np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
```

> **Lý do decode 2 lần**: `FatigueDetector.process()` và `SeatbeltDetector.process()`
> mỗi bên tự decode JPEG bên trong → tổng cộng 3 lần decode/frame. Chi phí
> ~1ms/decode, chấp nhận được để giữ nguyên code AI gốc. Nếu cần tối ưu sau,
> có thể thêm method `process_bgr()` vào detector mà không phá vỡ logic cũ.

---

### 2.5 File SỬA: `app/core/config.py`

**Thêm các env var mới** vào class `Settings`:

```python
# ── Video file input (TS-merged-monitoring) ─────────────────────
VIDEO_PATH: str = os.getenv("VIDEO_PATH", "")
VIDEO_LOOP: bool = os.getenv("VIDEO_LOOP", "false").lower() == "true"
VIDEO_START_FRAME: int = int(os.getenv("VIDEO_START_FRAME", "0"))
ENABLE_DISPLAY: bool = os.getenv("ENABLE_DISPLAY", "true").lower() == "true"

# ── Seatbelt detection (TS-merged-monitoring) ───────────────────
SEATBELT_MODEL_PATH: str = os.getenv("SEATBELT_MODEL_PATH", "best_1.pt")
SEATBELT_CONFIDENCE_THRESHOLD: float = float(os.getenv("SEATBELT_CONFIDENCE_THRESHOLD", "0.3"))
SEATBELT_WARNING_FRAMES: int = int(os.getenv("SEATBELT_WARNING_FRAMES", "10"))
```

---

### 2.6 File SỬA: `app/messaging/publisher.py`

**Thay đổi nhỏ**: cho phép ghi đè `ROUTING_KEY` từ bên ngoài (để dùng chung
class `ResultPublisher` cho cả `driver.result` và `seatbelt.result`).

Hiện tại `ROUTING_KEY` là class attribute `"driver.result"`. Sửa thành:
```python
class ResultPublisher:
    EXCHANGE: str = "adas.exchange"
    EXCHANGE_TYPE: str = "topic"

    def __init__(self, connection_manager, routing_key: str = "driver.result"):
        self._routing_key = routing_key
        ...
```

Trong orchestrator, khởi tạo 2 instance:
```python
self._publisher = ResultPublisher(self._connection_manager, routing_key="driver.result")
self._seatbelt_publisher = ResultPublisher(self._connection_manager, routing_key="seatbelt.result")
```

---

### 2.7 File SỬA: `app/api/fatigue.py`

**Thêm endpoints**:
```python
@router.post("/video/pause")
def pause_video():
    orchestrator = get_orchestrator()
    if orchestrator.video_reader:
        orchestrator.video_reader.pause()
        return {"status": "paused"}
    return {"status": "no_video_mode"}

@router.post("/video/resume")
def resume_video():
    orchestrator = get_orchestrator()
    if orchestrator.video_reader:
        orchestrator.video_reader.resume()
        return {"status": "resumed"}
    return {"status": "no_video_mode"}
```

**Cập nhật `/health`**: thêm `seatbelt_model_loaded`, `frame_source` (webcam/video).

**Cập nhật `/stats`**: thêm `video_current_frame`, `video_total_frames`,
`video_fps`, thống kê seatbelt (`seatbelt_ok_count`, `seatbelt_missing_count`).

---

### 2.8 File SỬA: `requirements.txt`

Thêm dòng:
```
ultralytics==8.3.67
```

(Khớp với version đang dùng trong seatbelt_service.)

---

### 2.9 File MỚI: `best_1.pt`

Copy từ `services/seatbelt_service/best_1.pt` vào `services/driver-service/best_1.pt`.

---

## 3. Logic + AI

### 3.1 Drowsiness Pipeline (GIỮ NGUYÊN)

| Layer | Model/Algorithm | Input | Output | Threshold |
|---|---|---|---|---|
| Landmark | MediaPipe Face Landmarker (478 landmarks) | BGR frame (H×W×3) | 478 landmarks + transformation matrix | — |
| Feature | `calculate_ear()` | 6 eye landmarks | EAR (0.0-1.0) | `EAR_THRESHOLD=0.22` |
| Feature | `calculate_mar()` | 8 mouth landmarks | MAR (0.0-1.0) | `MAR_THRESHOLD=0.6` |
| Feature | `extract_head_pose()` | transformation matrix 4×4 | (yaw, pitch, roll) degrees | `HEAD_POSE_PITCH_THRESHOLD=20°`, `YAW=25°` |
| Feature | `FeatureService.extract()` | landmarks → 40 features | `FeatureVector` (40 float fields) | — |
| Classifier | `RandomForestClassifier` (sklearn) | 40 features | `ClassificationResult` | `PERCLOS_*_MAX` thresholds cho rule-based fallback |
| Complexity | — | — | — | MediaPipe ~15-30ms, RF <1ms |

### 3.2 Seatbelt Pipeline (MỚI)

| Layer | Model/Algorithm | Input | Output | Threshold |
|---|---|---|---|---|
| Detection | YOLO (ultralytics) `best_1.pt` | BGR frame (H×W×3) | List of detections (class_id, confidence, bbox) | `SEATBELT_CONFIDENCE_THRESHOLD=0.3` |
| Classification | Class ID check | detections | `has_seatbelt: bool` | class_id == 6 → seatbelt |
| Warning | Consecutive frame counter | `has_seatbelt: bool` | `warning: bool` | `SEATBELT_WARNING_FRAMES=10` |
| Complexity | — | — | — | YOLO ~20-50ms (GPU) / ~100-300ms (CPU) |

### 3.3 Tổng inference time ước tính

| Cấu hình | MediaPipe | YOLO | Tổng/frame | FPS khả thi |
|---|---|---|---|---|
| CPU only | ~30ms | ~200ms | ~230ms | ~4 fps |
| GPU (CUDA) | ~15ms | ~30ms | ~45ms | ~22 fps |
| GPU + TensorRT | ~10ms | ~15ms | ~25ms | ~40 fps |

---

## 4. API Contract

### 4.1 Giữ nguyên

| Method | Path | Response | Ghi chú |
|---|---|---|---|
| `GET` | `/health` | `{status, service, model_loaded, seatbelt_model_loaded, frame_source, camera_connected}` | Mở rộng |
| `GET` | `/stats` | `{uptime, total_frames, avg_inference_ms, ..., seatbelt_ok_count, seatbelt_missing_count, video_*}` | Mở rộng |
| `GET` | `/frame` | `image/jpeg` | Debug, giữ nguyên |

### 4.2 Thêm mới

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/video/pause` | — | `{status: "paused" \| "no_video_mode"}` |
| `POST` | `/video/resume` | — | `{status: "resumed" \| "no_video_mode"}` |

---

## 5. Thread Model

```
Thread 1: "MainThread"         — FastAPI (uvicorn), xử lý HTTP requests
Thread 2: "camera-capture"     — CameraCaptureService HOẶC VideoFileReader
           (daemon)
Thread 3: "ai-worker"          — Nhận JPEG từ queue, chạy CẢ 2 model,
           (daemon)              publish kết quả, push vào display queue
Thread 4: "display"            — Nhận rendered frame từ display_queue,
           (daemon)              gọi cv2.imshow(), xử lý phím
```

**Thread-safety**:
- `queue.Queue` là thread-safe (dùng cho frame_queue, display_queue).
- `cv2.VideoCapture` được sở hữu độc quyền bởi capture thread.
- `cv2.imshow()` được gọi độc quyền bởi display thread.
- MediaPipe và YOLO model đều được gọi trong ai-worker thread (tuần tự,
  không concurrent giữa 2 model) → không cần lock cho model.

---

## 6. Rủi ro & câu hỏi mở

| # | Rủi ro | Mitigation |
|---|---|---|
| 1 | `cv2.imshow()` từ non-main thread có thể không hoạt động trên macOS/Linux | Chấp nhận — service chạy trên Windows (theo env). Nếu cần cross-platform, thêm option headless mode (`ENABLE_DISPLAY=false`) và lưu video output thay vì hiển thị. |
| 2 | YOLO và MediaPipe cùng chiếm GPU memory → OOM | Chạy tuần tự, không concurrent. Nếu OOM vẫn xảy ra, thêm env var `YOLO_DEVICE=cpu` để force YOLO chạy trên CPU. |
| 3 | Double JPEG decode (3 lần/frame) lãng phí CPU | Chi phí <3ms tổng, chấp nhận được. Tối ưu sau nếu cần (thêm `process_bgr()` method). |
| 4 | Video FPS cao hơn inference rate → backlog | Queue maxsize=2 → auto-drop frame. Phù hợp với thiết kế hiện tại của `CameraCaptureService`. |

---

## 7. Ảnh hưởng tới service khác

- **driver-service**: được sửa đổi (thêm file mới, sửa orchestrator/config/api).
- **seatbelt_service**: **KHÔNG bị sửa** — chỉ copy model + code tham khảo.
- **services-map.md**: cập nhật driver-service: thêm seatbelt detection, video file input, port giữ nguyên 8001.

---

## 8. Trạng thái xác nhận

`[ ] Chưa xác nhận` / `[x] Đã xác nhận bởi người dùng ngày ___`
