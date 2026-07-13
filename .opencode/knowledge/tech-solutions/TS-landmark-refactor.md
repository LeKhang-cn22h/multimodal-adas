# TS-landmark-refactor: Tách Face Landmarker thành service riêng

## Thuộc Feature
`.opencode/knowledge/features/FEAT-landmark-refactor.md`

## Kiến trúc

### Luồng dữ liệu (sau refactor)

```
JPEG bytes (từ RabbitMQ consumer)
        │
        ▼
FatigueDetector._decode_jpeg()        ← giữ nguyên trong FatigueDetector
        │
        ▼  numpy array (BGR)
FaceLandmarkerService.detect()        ← TÁCH RA service riêng
        │
        ▼  FaceLandmarkerResult
FatigueDetector._run_inference()      ← nhận result thay vì gọi MediaPipe trực tiếp
        │
        ▼  dict (sleepy, confidence)
ResultPublisher.publish()
```

### Trước / Sau

| Thành phần | Trước (hiện tại) | Sau (refactor) |
|---|---|---|
| Model load | `FatigueDetector.load_model()` | `FaceLandmarkerService.load_model()` |
| MediaPipe import | Trong `fatigue_detector.py` (line 15-26) | Chỉ trong `mediapipe_service.py` |
| Inference call | `FatigueDetector._run_inference()` gọi trực tiếp `self._landmarker.detect_for_video()` | `FaceLandmarkerService.detect()` được inject vào `FatigueDetector` |
| Result type | Raw MediaPipe object | `FaceLandmarkerResult` (dataclass) |
| Transformation matrix | Không lưu (không dùng) | Lưu trong `FaceLandmarkerResult` để Head Pose dùng sau |

### File sẽ tạo/sửa

| File | Hành động | Trách nhiệm |
|---|---|---|
| `services/mediapipe_service.py` | **TẠO MỚI** | `FaceLandmarkerService` — load model, detect, trả `FaceLandmarkerResult`. Không biết gì về EAR/drowsiness. |
| `services/fatigue_detector.py` | **SỬA** | Bỏ import `mediapipe` trực tiếp. Nhận `FaceLandmarkerService` qua constructor. `_run_inference()` gọi `self._landmarker_service.detect()` thay vì tự tạo `mp.Image` + `detect_for_video()`. |
| `messaging/orchestrator.py` | **SỬA** | Tạo `FaceLandmarkerService` trước, inject vào `FatigueDetector`. Thêm property `landmark_service`. |
| `api/fatigue.py` | **SỬA** | `GET /health` đọc `orchestrator.landmark_service.is_loaded` thay vì `orchestrator.detector.is_loaded` |
| `core/config.py` | **KHÔNG SỬA** | `MODEL_PATH` đã có sẵn, không cần thêm |
| `utils/ear.py` | **KHÔNG SỬA** | Pure function, không liên quan tới refactor này |
| `messaging/consumer.py` | **KHÔNG SỬA** | Chỉ gọi `detector.process()`, interface không đổi |
| `messaging/publisher.py` | **KHÔNG SỬA** | Không liên quan |

### Dependency graph mới

```
messaging/orchestrator.py
    ├── FaceLandmarkerService  (KHỞI TẠO TRƯỚC)
    │       └── model: face_landmarker.task
    ├── FatigueDetector  (NHẬN FaceLandmarkerService qua constructor)
    │       ├── FaceLandmarkerService (injected)
    │       ├── utils/ear.py (pure function)
    │       └── core/config.py (thresholds)
    ├── FrameConsumer (nhận FatigueDetector)
    └── ResultPublisher
```

Đúng DIP: `FatigueDetector` phụ thuộc vào abstraction (interface của `FaceLandmarkerService`), không phụ thuộc vào MediaPipe concrete.

## Logic + AI

### Model

| Thuộc tính | Giá trị |
|---|---|
| **Model** | MediaPipe Face Landmarker (`face_landmarker.task`) |
| **Nguồn** | Google MediaPipe (Apache 2.0 license), đã có sẵn trong `driver-service/` |
| **Phiên bản** | Float16, task file format |
| **Load** | 1 lần trong `lifespan` → `FaceLandmarkerService.load_model()`, không load lại |
| **Mode** | `VisionRunningMode.VIDEO` (dùng `detect_for_video`, yêu cầu timestamp_ms) |

### Input / Output

#### `FaceLandmarkerService.detect()`

| | Kiểu | Mô tả |
|---|---|---|
| **Input: frame** | `np.ndarray` | Ảnh BGR, shape `(H, W, 3)`, uint8. Service tự chuyển sang RGB + `mp.Image` |
| **Input: timestamp_ms** | `int` | Timestamp cho `detect_for_video()` (miliseconds), do `FatigueDetector` sinh từ `time.time() * 1000` |
| **Output** | `FaceLandmarkerResult` | Dataclass (xem bên dưới) |

#### `FaceLandmarkerResult` (dataclass) — định nghĩa đầy đủ

Đây là internal DTO, **không serialize qua JSON**, dùng riêng trong `services/` và `messaging/` layer. Tất cả field được liệt kê:

```python
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import mediapipe as mp

@dataclass
class FaceLandmarkerResult:
    """Kết quả từ FaceLandmarkerService.detect().

    Tất cả field lấy TRỰC TIẾP từ output của MediaPipe Face Landmarker,
    không qua biến đổi trung gian nào.
    """

    # ── Field 1: cờ phát hiện mặt ──────────────────────────────────
    face_detected: bool
    # True nếu có ít nhất 1 khuôn mặt trong frame.
    # False nếu không có mặt → tất cả field khác = None.

    # ── Field 2: facial landmarks (478 điểm) ───────────────────────
    landmarks: Optional[list]
    # list[mp.tasks.vision.NormalizedLandmark], độ dài = 478.
    # Mỗi phần tử có .x, .y, .z (tọa độ chuẩn hóa [0,1]).
    # Lấy từ: result.face_landmarks[0] (chỉ lấy mặt đầu tiên, num_faces=1).
    # None nếu face_detected=False.

    # ── Field 3: transformation matrix cho Head Pose ───────────────
    transformation_matrix: Optional[np.ndarray]
    # Ma trận biến đổi 4×4 (float64), shape (4, 4).
    # Lấy từ: result.facial_transformation_matrixes[0]
    #         (MediaPipe field gốc tên là facial_transformation_matrixes
    #          — số nhiều — ta lấy phần tử [0] cho mặt đầu tiên).
    # Dùng để suy ra Yaw/Pitch/Roll trong FEAT-feature-extraction
    # theo ADR-004 (không cần solvePnP).
    # None nếu face_detected=False HOẶC MediaPipe không trả về matrix.
```

**Xác nhận theo yêu cầu rà soát**:

| Yêu cầu | Trạng thái | Ghi chú |
|---|---|---|
| Field `transformation_matrix` có mặt trong dataclass | ✅ CÓ | Field 3, kiểu `np.ndarray \| None`, shape (4,4) |
| Lấy trực tiếp từ MediaPipe output | ✅ ĐÚNG | `result.facial_transformation_matrixes[0]` |
| Là input bắt buộc cho Head Pose (FEAT-feature-extraction) | ✅ XÁC NHẬN | Theo ADR-004, `utils/headpose.py` sẽ nhận matrix này để decompose ra Euler angles |
| Đầy đủ 3 field (face_detected, landmarks, transformation_matrix) | ✅ ĐỦ | Dataclass có đúng 3 field như trên, không thiếu, không thừa |

> **Lý do dùng dataclass thay vì Pydantic**: `transformation_matrix` là `np.ndarray`, không serialize được tự nhiên qua Pydantic. Đây là internal DTO, không expose qua API/JSON.

#### `FaceLandmarkerService` public methods

| Method | Input | Output | Mô tả |
|---|---|---|---|
| `__init__(model_path: str)` | `str` | — | Lưu path, chưa load model |
| `load_model() -> None` | — | — | Tạo `FaceLandmarker.create_from_options()`, gán vào `self._landmarker` |
| `detect(frame, timestamp_ms)` | `np.ndarray`, `int` | `FaceLandmarkerResult` | BGR → RGB → `mp.Image` → `detect_for_video()` → extract landmarks + matrix |
| `close_model() -> None` | — | — | Gọi `self._landmarker.close()` |
| `is_loaded -> bool` | — | `bool` | Property, True nếu model đã load |

### Ngưỡng (threshold)

Refactor này **không thêm threshold mới**. Các threshold hiện tại trong `core/config.py` (`EAR_THRESHOLD=0.22`, `DROWSY_FRAMES=60`, `SLIDING_WINDOW_SIZE=90`) **giữ nguyên**, vẫn do `FatigueDetector` quản lý.

### Độ phức tạp / Hiệu năng

| Chỉ số | Giá trị | Ghi chú |
|---|---|---|
| **Model load time** | ~500ms (1 lần) | Không đổi so với hiện tại |
| **Inference latency** | ~8-15ms/frame | Không đổi (vẫn cùng model, cùng API) |
| **Overhead thêm** | 0 (zero) | Chỉ tách class, không thêm layer trung gian, không thêm copy dữ liệu |
| **Memory** | ~10MB (model) | Không đổi, model load 1 instance duy nhất |

Refactor này là **pure structural change** — không thay đổi thuật toán, không thêm network call, không thêm serialization. Latency giữ nguyên.

## API Contract

### Không thay đổi HTTP API

| Endpoint | Method | Trạng thái |
|---|---|---|
| `GET /health` | GET | Sửa nhẹ: đọc `orchestrator.landmark_service.is_loaded` thay vì `orchestrator.detector.is_loaded`. Response schema không đổi |
| `GET /stats` | GET | Không sửa |

**Response schema** (không đổi):

```json
// GET /health
{
  "status": "healthy" | "degraded",
  "service": "driver-service",
  "model_loaded": true | false
}
```

### Không thay đổi RabbitMQ API

- Queue `driver.frames`: giữ nguyên (consume JPEG)
- Routing `driver.result`: giữ nguyên (publish dict `{frame_id, timestamp, sleepy, confidence}`)

## Rủi ro & câu hỏi mở

### Rủi ro thấp

| Rủi ro | Mức độ | Giảm thiểu |
|---|---|---|
| `NormalizedLandmark` là MediaPipe type → leak abstraction sang `FatigueDetector` | Thấp | OK vì `utils/ear.py` đã phụ thuộc vào `.x`, `.y` của `NormalizedLandmark`. Nếu sau này đổi model, sửa cả 2 file. |
| `facial_transformation_matrixes` có thể rỗng | Thấp | `FaceLandmarkerService` check: nếu không có mặt → `transformation_matrix=None`; nếu có mặt nhưng không có matrix → `None` (an toàn) |

### Phạm vi của TS này đối với ADR-003

**ADR-003 cam kết**: dời `app/messaging/` (connection, publisher, consumer, orchestrator) vào `app/services/`.

**TS-landmark-refactor**: **KHÔNG thực hiện việc dời này.** Lý do:
- TS này chỉ refactor Face Landmarker → `FaceLandmarkerService`, phạm vi giới hạn trong `services/mediapipe_service.py` + `fatigue_detector.py` + `orchestrator.py`.
- File `messaging/consumer.py` và `messaging/publisher.py` **không bị đụng tới** — chúng vẫn import `FatigueDetector` và `ResultPublisher` như cũ, interface không đổi.
- Việc dời toàn bộ `messaging/` vào `services/` là 1 refactor lớn hơn, ảnh hưởng tới cả `camera-service` (cũng có `messaging/` riêng), cần 1 Feature + Tech Solution riêng.

> ⚠️ **Đã thêm vào `open-questions.md`**: "ADR-003 phần dời messaging/ vào services/ chưa có Tech Solution/Feature nào phụ trách, cần bổ sung trước khi coi Driver Drowsiness Detection Module là hoàn tất."

## Ảnh hưởng tới service khác

**Không ảnh hưởng.** driver-service là service duy nhất bị thay đổi. HTTP API và RabbitMQ contract không đổi.

`.opencode/knowledge/services-map.md` — **không cần cập nhật** (API không đổi).

## Trạng thái xác nhận

`[x] Đã xác nhận bởi người dùng ngày 2026-07-05`
