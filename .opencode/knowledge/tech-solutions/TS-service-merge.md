# TS-service-merge: Gộp camera-service vào driver-service (ADR-006)

## Thuộc Feature
`.opencode/knowledge/features/FEAT-service-merge.md`

## Kiến trúc

### Tổng quan

Gộp toàn bộ chức năng webcam capture từ camera-service cũ vào driver-service. Pipeline mới: **capture thread → queue.Queue → worker thread (AI + publish)**. Đây là kiến trúc 2-thread với internal queue, giải quyết đồng thời 3 ràng buộc thread-safety: `cv2.VideoCapture.read()` (chỉ gọi từ 1 thread), MediaPipe Face Landmarker (không thread-safe), pika channel (chỉ gọi publish từ thread tạo channel).

**Phạm vi**: driver-service (mở rộng) + xoá toàn bộ camera-service.

### Kiến trúc thread (2-thread + queue)

```
┌──────────────────────────────────────────────────────┐
│                   DRIVER-SERVICE                      │
│                                                      │
│  ┌─────────────────────────┐  ┌────────────────────┐ │
│  │   CAPTURE THREAD         │  │  WORKER THREAD      │ │
│  │                          │  │                     │ │
│  │  cv2.VideoCapture(0)    │  │  queue.Queue.get()  │ │
│  │  while True:             │  │     │                │ │
│  │    read() → BGR          │  │     ▼                │ │
│  │    imencode() → JPEG     │  │  FatigueDetector    │ │
│  │    queue.put(jpeg) ──────┼──▶  .process(jpeg)    │ │
│  │                          │  │     │                │ │
│  │                          │  │     ▼                │ │
│  │  (update latest_jpeg     │  │  ResultPublisher    │ │
│  │   + fps_stats under lock)│  │  .publish(result)   │ │
│  │                          │  │     │                │ │
│  │  OWNED: cv2.VideoCapture │  │     ▼                │ │
│  │          threading.Lock  │  │  RabbitMQ           │ │
│  └─────────────────────────┘  │  driver.result       │ │
│                                │                     │ │
│                                │  OWNED: MediaPipe   │ │
│                                │          pika ch    │ │
│  ┌─────────────────────────┐  └────────────────────┘ │
│  │   FASTAPI (main thread)  │                         │
│  │  GET /health             │                         │
│  │  GET /stats              │                         │
│  │  GET /frame (latest_jpeg)│                         │
│  └─────────────────────────┘                          │
└──────────────────────────────────────────────────────┘
```

**Thread ownership & safety**:

| Tài nguyên | Owner thread | Thread khác có được gọi? |
|---|---|---|
| `cv2.VideoCapture` | Capture thread | ❌ Không |
| `threading.Lock` (latest_jpeg, fps) | Capture thread (write) + Main thread (read) | ✅ Có lock |
| `queue.Queue` | Capture (put) + Worker (get) | ✅ Built-in thread-safe |
| MediaPipe `FaceLandmarker` | Worker thread | ❌ Không |
| pika channel (`ResultPublisher`) | Worker thread | ❌ Không |
| FastAPI routes | Main thread (asyncio) | ✅ |

### Luồng dữ liệu

```
Camera (USB)
    │
    ▼
Capture Thread
    │  cv2.VideoCapture.read() → BGR
    │  cv2.imencode(".jpg") → JPEG bytes
    │
    ├── (1) queue.Queue.put(jpeg_bytes)     → Worker Thread xử lý
    │
    └── (2) Cập nhật latest_jpeg (có lock)  → GET /frame debug
               Cập nhật fps_stats (có lock)  → GET /stats
    │
    ▼
Worker Thread
    │  queue.Queue.get() → JPEG bytes
    │  FatigueDetector.process(jpeg, frame_id, timestamp)
    │       ├── FaceLandmarkerService.detect()
    │       ├── FeatureService.extract() → 40 features
    │       └── IClassifier.classify() → ClassificationResult
    │  ResultPublisher.publish(result)
    │
    ▼
RabbitMQ "driver.result" → consumer ADAS bên ngoài
```

### Cơ chế chống backlog

Nếu AI xử lý chậm hơn tốc độ webcam (30 FPS), frame sẽ dồn lại. Cơ chế **duy nhất**: capture thread dùng `queue.Queue(maxsize=MAX_QUEUE_SIZE)` (default 2) + `put_nowait()`. Khi queue đầy, `put_nowait` raise `queue.Full` → capture bỏ qua frame đó, tăng `dropped_frame_count`. Worker thread chỉ đơn giản `get()` và xử lý — không có logic drop bổ sung nào phía worker.

- **Capture side**: `put_nowait` — nếu queue đầy, frame bị drop NGAY LẬP TỨC tại capture, webcam không bị block, FPS webcam giữ ổn định.
- **Worker side**: chỉ `get()` — không kiểm tra `qsize`, không drop. Vì `maxsize` đã giới hạn queue, worker luôn nhận frame gần nhất có thể (tối đa 2 frame trong queue).
- **Theo dõi**: `dropped_frame_count` (tăng mỗi lần `queue.Full`) → expose qua `GET /stats` để biết tỉ lệ frame rớt. Đây là chỉ số quan trọng: nếu tỉ lệ drop > 0% kéo dài, pipeline AI không theo kịp webcam → cần tối ưu hoặc giảm FPS.

### File sẽ tạo/sửa/xoá

| File | Hành động | Mô tả |
|---|---|---|
| `app/services/camera_capture_service.py` | **TẠO MỚI** | `CameraCaptureService`: mở webcam, background capture thread, encode JPEG, `queue.Queue` đẩy frame cho worker, thread-safe `latest_jpeg` + fps stats |
| `app/messaging/orchestrator.py` | **SỬA** | Thêm `CameraCaptureService` → start capture thread + worker thread. Xoá `FrameConsumer`. Đổi tên thành `DriverOrchestrator` cho rõ nghĩa (hoặc giữ tên cũ, quyết định khi implement) |
| `app/messaging/consumer.py` | **XOÁ** | Không còn FrameConsumer — frame đến từ camera nội bộ, không từ RabbitMQ |
| `app/services/camera_client.py` | **XOÁ** | Legacy HTTP client gọi camera-service cũ |
| `app/api/fatigue.py` | **SỬA** | Thêm `GET /frame` (trả `latest_jpeg`), cập nhật `/health` (thêm `camera_connected`), `/stats` (thêm `camera_fps`) |
| `app/core/config.py` | **SỬA** | Thêm `CAMERA_INDEX`, `FRAME_WIDTH`, `FRAME_HEIGHT`, `JPEG_QUALITY`, `MAX_QUEUE_SIZE` |
| `app/messaging/publisher.py` | **KIỂM TRA** | Xác nhận chỉ còn `ResultPublisher` (publish JSON), không còn `FramePublisher` (publish JPEG) — nếu có, xoá phần FramePublisher |
| `services/camera-service/` | **XOÁ** | Toàn bộ thư mục |
| `desktop_monitor.py` | **XOÁ** | Không port sang driver-service. Nếu cần debug, dùng `GET /frame` |
| `docker-compose.yml` | **SỬA** | Bỏ service `camera-service`, driver-service thêm device mapping `/dev/video0` |

### Dependency graph

```
CameraCaptureService (app/services/camera_capture_service.py)
    ├── cv2 (VideoCapture, imencode)
    ├── threading (Thread, Lock, Event)
    ├── queue.Queue
    └── app.core.config (CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT, JPEG_QUALITY, MAX_QUEUE_SIZE)

DriverOrchestrator (app/messaging/orchestrator.py)
    ├── CameraCaptureService
    ├── FaceLandmarkerService
    ├── FeatureService
    ├── IClassifier (RFClassifier | RuleBasedClassifier)
    ├── FatigueDetector
    ├── ResultPublisher
    ├── RabbitMQConnectionManager
    └── queue.Queue (shared giữa capture thread và worker thread)

FatigueDetector (app/services/fatigue_detector.py)
    └── KHÔNG SỬA — đã nhận IClassifier qua constructor (DIP)
```

## Logic + AI

Không có thuật toán mới — feature này là thay đổi kiến trúc truyền dữ liệu, không thay đổi logic AI.

### CameraCaptureService

```python
class CameraCaptureService:
    """Manages webcam capture in a background thread.

    Thread-safe: capture thread writes latest_jpeg + fps under lock;
    main thread reads for GET /frame and GET /stats.

    Pushes JPEG frames to queue.Queue for the worker thread to process.
    """

    def __init__(self, settings, frame_queue: queue.Queue):
        self._camera_index = settings.CAMERA_INDEX        # default 0
        self._jpeg_quality = settings.JPEG_QUALITY         # default 85
        self._frame_width = settings.FRAME_WIDTH           # default 640
        self._frame_height = settings.FRAME_HEIGHT         # default 480
        self._max_queue_size = settings.MAX_QUEUE_SIZE     # default 2

        self._capture: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frame_queue = frame_queue

        # Thread-safe state (read under lock)
        self._latest_jpeg: Optional[bytes] = None
        self._fps: float = 0.0
        self._frame_id: int = 0
        self._is_running: bool = False
        self._dropped_frames: int = 0   # tăng mỗi lần queue.Full → frame bị bỏ

    # --- Public API (main thread) ---
    def start(self) -> None: ...
    def stop(self) -> None: ...

    @property
    def latest_jpeg(self) -> Optional[bytes]: ...
    @property
    def fps(self) -> float: ...
    @property
    def is_running(self) -> bool: ...
    @property
    def dropped_frames(self) -> int: ...
```

### Worker thread (trong orchestrator)

```python
def _worker_loop(
    frame_queue: queue.Queue,
    detector: FatigueDetector,
    publisher: ResultPublisher,
    stop_event: threading.Event,
) -> None:
    """Worker thread: read frames from queue, run AI, publish results.

    No drop logic on worker side — queue maxsize is enforced by capture
    thread via put_nowait, so queue size is always ≤ MAX_QUEUE_SIZE.
    """
    frame_id = 0
    while not stop_event.is_set():
        try:
            jpeg_bytes = frame_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        timestamp = time.time()
        result = detector.process(jpeg_bytes, frame_id, timestamp)
        publisher.publish(result)
        frame_id += 1
```

### Cấu hình mới trong `core/config.py`

```python
# ── Camera capture (TS-service-merge) ──────────────────────────
CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))
FRAME_WIDTH: int = int(os.getenv("FRAME_WIDTH", "640"))
FRAME_HEIGHT: int = int(os.getenv("FRAME_HEIGHT", "480"))
JPEG_QUALITY: int = int(os.getenv("JPEG_QUALITY", "85"))
MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", "2"))
```

### Độ phức tạp & latency estimate

| Thành phần | Thời gian/frame | Ghi chú |
|---|---|---|
| `cv2.VideoCapture.read()` | ~1ms | Phụ thuộc webcam |
| `cv2.imencode()` (640×480 JPEG 85) | ~3ms | |
| `queue.Queue.put()` / `get()` | ~0.001ms | |
| AI pipeline (MediaPipe + 40 features + RF) | ~15-20ms | Đã đo từ trước |
| `ResultPublisher.publish()` | ~0.5ms | |
| **Tổng pipeline** | **~20-25ms** | Đủ cho 30 FPS (33ms/frame) |

Rủi ro: nếu AI pipeline > 33ms, worker sẽ drop frame cũ → FPS pipeline giảm, nhưng capture không bị ảnh hưởng.

## API Contract

### `GET /health` (cập nhật)

```json
{
  "status": "healthy",
  "service": "driver-service",
  "model_loaded": true,
  "classification_method": "random_forest",
  "camera_connected": true
}
```

### `GET /stats` (cập nhật)

```json
{
  "uptime": 123.45,
  "total_frames": 1234,
  "avg_inference_ms": 18.2,
  "classification_method": "random_forest",
  "fatigue_level_distribution": {"Awake": 800, "Tired": 200, ...},
  "camera_fps": 29.8,
  "camera_dropped_frames": 5
}
```

### `GET /frame` (mới — debug)

Trả về `image/jpeg` — `latest_jpeg` từ `CameraCaptureService`. Dùng để kiểm tra webcam hoạt động mà không cần chạy toàn bộ pipeline.

Response: `200 OK` với `Content-Type: image/jpeg`, body là JPEG bytes.

Nếu camera chưa start: `503 Service Unavailable`.

## Rủi ro & câu hỏi mở

| Rủi ro | Mức độ | Giảm thiểu |
|---|---|---|
| **AI pipeline > 33ms → drop frame** | Thấp | Worker drop-oldest, capture không bị block. Pipeline vẫn chạy ở FPS tối đa có thể. |
| **pika channel dùng sai thread** | Thấp | Worker thread tạo channel trong `start()`, chỉ worker gọi `publish()`. Không share channel với main thread. |
| **MediaPipe thread conflict** | Thấp | Chỉ worker thread gọi `FaceLandmarker.detect()`. Không thread nào khác đụng vào. |
| **Queue memory nếu worker chậm** | Thấp | `maxsize=MAX_QUEUE_SIZE` (default 2) → tối đa 2 frame trong queue, ~100KB. |
| **Webcam disconnect** | Thấp | Auto-reconnect logic từ CameraManager cũ được giữ nguyên. |

Không có câu hỏi mở — mọi quyết định đã được chốt trong Tech Solution này.

## Ảnh hưởng tới service khác

- **camera-service**: XOÁ toàn bộ.
- **driver-service**: Mở rộng trách nhiệm (thêm webcam capture).
- **frontend / consumer ADAS**: `driver.result` schema không đổi → không ảnh hưởng.
- **lane-service, vehicle-service**: Không ảnh hưởng (chưa có code).

Cập nhật `.opencode/knowledge/services-map.md`:
- Dòng camera-service đã đánh dấu ~~MERGED~~ (đã làm trong bước trước).
- Dòng driver-service: API thêm `GET /frame`, Messaging chỉ còn "Publish: driver.result".

## Trạng thái xác nhận

`[x] Đã xác nhận bởi người dùng ngày 2026-07-11
`
