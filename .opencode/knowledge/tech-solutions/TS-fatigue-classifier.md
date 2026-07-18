# TS-fatigue-classifier: Rule-Based Classifier + Pipeline Integration

## Thuộc Feature
`.opencode/knowledge/features/FEAT-fatigue-classifier.md`

## Kiến trúc

### Tổng quan

Tích hợp `RuleBasedClassifier` vào `FatigueDetector`, thay thế logic EAR-threshold đơn giản hiện tại bằng classifier 4 cấp PERCLOS-based. Đây là bước trung gian — cho ra sản phẩm chạy được ngay với rule-based, trước khi tích hợp Random Forest (FEAT-rf-integration).

**Phạm vi**: driver-service ONLY.

### File sẽ tạo/sửa

| File | Hành động | Mô tả |
|---|---|---|
| `app/services/rule_based_classifier.py` | **TẠO MỚI** | `RuleBasedClassifier` — implement công thức 4 cấp từ REQ AC-3.5 |
| `app/services/classifier_interface.py` | **TẠO MỚI** | Abstract base class `IClassifier` với method `classify(features: FeatureVector) -> ClassificationResult` |
| `app/schemas/classification_result.py` | **TẠO MỚI** | Pydantic/dataclass `ClassificationResult`: `fatigue_score`, `fatigue_level`, `confidence`, `classification_method` |
| `app/services/fatigue_detector.py` | **SỬA** | Constructor nhận thêm `classifier: IClassifier`. `_run_inference()` gọi `classifier.classify(fv)` thay vì EAR-threshold thủ công. Giữ `FeatureService.extract()` để lấy `FeatureVector`. |
| `app/messaging/orchestrator.py` | **SỬA** | Wire `RuleBasedClassifier` → inject vào `FatigueDetector` |
| `app/messaging/consumer.py` | **SỬA** | Cập nhật publish schema mới (JSON có `fatigue_score`, `fatigue_level`, `features`) |
| `app/core/config.py` | **SỬA** | Thêm threshold cho rule-based: `PERCLOS_AWAKE`, `PERCLOS_TIRED`, `PERCLOS_DROWSY`, `PERCLOS_DANGEROUS`, `MICROSLEEP_SECONDS`, `YAWN_COUNT_WINDOW`, `HEAD_TILT_SECONDS` |

### Luồng dữ liệu mới

```
FatigueDetector.process(jpeg_bytes, frame_id, timestamp)
    │
    ├── 1. _decode_jpeg(jpeg_bytes) → BGR frame
    ├── 2. _landmark_service.detect(frame) → FaceLandmarkerResult
    ├── 3. _feature_service.extract(result) → FeatureVector (40 fields)
    │
    └── 4. _classifier.classify(fv) → ClassificationResult
            │
            ├── fatigue_score: int (0-100)
            ├── fatigue_level: "Awake" | "Tired" | "Drowsy" | "Dangerous" | "Unknown"
            ├── confidence: float (0.0-1.0)
            └── classification_method: "rule_based"
            │
            ▼
        _build_result() → dict → ResultPublisher → RabbitMQ driver.result
```

### Dependency graph

```
IClassifier (app/services/classifier_interface.py)  ← abstract
    ↑
    │
RuleBasedClassifier (app/services/rule_based_classifier.py)
    ├── app.services.feature_service (FeatureVector — import type)
    ├── app.schemas.classification_result (ClassificationResult)
    └── app.core.config (thresholds)

FatigueDetector (app/services/fatigue_detector.py)
    ├── FaceLandmarkerService (inject)
    ├── FeatureService (inject)
    └── IClassifier (inject)          ← THAY ĐỔI: nhận classifier qua constructor
```

## Logic + AI

### 1. IClassifier Interface

```python
from abc import ABC, abstractmethod
from app.services.feature_service import FeatureVector
from app.schemas.classification_result import ClassificationResult

class IClassifier(ABC):
    @abstractmethod
    def classify(self, features: FeatureVector) -> ClassificationResult:
        """Classify fatigue from a 40-feature vector."""
        ...
```

### 2. ClassificationResult Schema

```python
from dataclasses import dataclass
from typing import Literal

FatigueLevel = Literal["Awake", "Tired", "Drowsy", "Dangerous", "Unknown"]

@dataclass
class ClassificationResult:
    fatigue_score: int           # 0-100, -1 if Unknown
    fatigue_level: FatigueLevel
    confidence: float            # 0.0-1.0
    classification_method: str   # "rule_based" | "random_forest"
    features: dict[str, float]   # snapshot of key features for debugging
```

### 3. RuleBasedClassifier — Công thức 4 cấp

Dựa trên REQ AC-3.5, phân loại theo PERCLOS kết hợp MAR (ngáp) và Head Pose (cúi/nghiêng đầu):

#### Input
- `FeatureVector` 40 fields — dùng các field: `perclos`, `ear_avg`, `mar`, `yaw`, `pitch`, `roll`

#### State cần duy trì (internal)
| State | Mục đích |
|---|---|
| `_mar_above_threshold_timestamps: deque[float]` | Theo dõi các lần MAR vượt ngưỡng trong 60 giây gần nhất |
| `_head_tilt_start: Optional[float]` | Timestamp bắt đầu cúi/nghiêng đầu bất thường |
| `_microsleep_start: Optional[float]` | Timestamp bắt đầu nhắm mắt liên tục |

#### Ngưỡng (từ config)

| Tham số | Default | Ý nghĩa |
|---|---|---|
| `PERCLOS_AWAKE_MAX` | 15.0 | PERCLOS < giá trị này → Awake |
| `PERCLOS_TIRED_MAX` | 25.0 | PERCLOS < giá trị này → Tired |
| `PERCLOS_DROWSY_MAX` | 40.0 | PERCLOS < giá trị này → Drowsy |
| `MAR_THRESHOLD` | 0.6 | MAR > giá trị này → đang ngáp |
| `YAWN_COUNT_THRESHOLD` | 3 | Số lần ngáp trong 60s → Tired |
| `YAWN_WINDOW_SECONDS` | 60 | Cửa sổ đếm ngáp |
| `HEAD_POSE_PITCH_THRESHOLD` | 20.0 | \|Pitch\| > giá trị này → cúi đầu bất thường |
| `HEAD_POSE_YAW_THRESHOLD` | 25.0 | \|Yaw\| > giá trị này → nghiêng đầu bất thường |
| `HEAD_TILT_DURATION_SECONDS` | 3.0 | Cúi/nghiêng ≥ thời gian này → Drowsy |
| `MICROSLEEP_EAR_THRESHOLD` | 0.22 | EAR < giá trị này → mắt đóng (dùng chung EAR_THRESHOLD) |
| `MICROSLEEP_DURATION_SECONDS` | 2.0 | Mắt đóng liên tục ≥ thời gian này → Dangerous |

#### Thuật toán `classify(fv: FeatureVector) -> ClassificationResult`

**Nguyên tắc**: Kiểm tra tuần tự từ mức nghiêm trọng nhất → thấp nhất. Mỗi mức được kích hoạt bởi PERCLOS trong khoảng **HOẶC** điều kiện phụ (microsleep / head-tilt / yawn). Đây là logic OR, khớp REQ AC-3.5.

```
Input: fv (40-field FeatureVector), current_timestamp

1. Trích xuất giá trị:
   perclos = fv.perclos
   ear_avg = fv.ear_avg
   mar     = fv.mar
   yaw     = fv.yaw
   pitch   = fv.pitch

2. Cập nhật state:

   a. MAR (ngáp):
      if mar > MAR_THRESHOLD:
          _mar_above_threshold_timestamps.append(current_timestamp)
      Xóa các timestamp cũ hơn YAWN_WINDOW_SECONDS
      yawn_count = len(_mar_above_threshold_timestamps)

   b. Head tilt:
      if |pitch| > HEAD_POSE_PITCH_THRESHOLD or |yaw| > HEAD_POSE_YAW_THRESHOLD:
          if _head_tilt_start is None:
              _head_tilt_start = current_timestamp
      else:
          _head_tilt_start = None
      head_tilt_duration = current_timestamp - _head_tilt_start if _head_tilt_start else 0

   c. Microsleep:
      if ear_avg < MICROSLEEP_EAR_THRESHOLD:
          if _microsleep_start is None:
              _microsleep_start = current_timestamp
      else:
          _microsleep_start = None
      microsleep_duration = current_timestamp - _microsleep_start if _microsleep_start else 0

3. Phân loại (kiểm tra tuần tự: Dangerous → Drowsy → Tired → Awake):

   ═══════════════════════════════════════════════════════════════
   CHECK 1 — Dangerous: PERCLOS > 40% HOẶC microsleep ≥ 2s
   ═══════════════════════════════════════════════════════════════

   if microsleep_duration >= MICROSLEEP_DURATION_SECONDS:
       # Microsleep → Dangerous, không phụ thuộc PERCLOS
       level = "Dangerous"
       score = 100
       confidence = min(1.0, microsleep_duration / MICROSLEEP_DURATION_SECONDS)

   elif perclos > PERCLOS_DROWSY_MAX:  # PERCLOS > 40% → Dangerous
       level = "Dangerous"
       score = min(100, int(perclos * 2.5))
       confidence = min(1.0, perclos / 60.0)

   ═══════════════════════════════════════════════════════════════
   CHECK 2 — Drowsy: PERCLOS 25-40% HOẶC head-tilt ≥ 3s
   ═══════════════════════════════════════════════════════════════

   elif perclos > PERCLOS_TIRED_MAX:  # PERCLOS trong (25%, 40%]
       # PERCLOS-driven Drowsy
       level = "Drowsy"
       score = 50 + int((perclos - PERCLOS_TIRED_MAX)
                        / (PERCLOS_DROWSY_MAX - PERCLOS_TIRED_MAX) * 25)
       confidence = 0.6 + (perclos - PERCLOS_TIRED_MAX) \
                        / (PERCLOS_DROWSY_MAX - PERCLOS_TIRED_MAX) * 0.3

   elif head_tilt_duration >= HEAD_TILT_DURATION_SECONDS:
       # Head-tilt-driven Drowsy (PERCLOS có thể thấp nhưng đầu bất thường)
       level = "Drowsy"
       score = 60  # midpoint của Drowsy range (51-75)
       confidence = min(0.85, head_tilt_duration / (HEAD_TILT_DURATION_SECONDS * 2))

   ═══════════════════════════════════════════════════════════════
   CHECK 3 — Tired: PERCLOS 15-25% HOẶC ngáp ≥ 3 lần/60s
   ═══════════════════════════════════════════════════════════════

   elif perclos > PERCLOS_AWAKE_MAX:  # PERCLOS trong (15%, 25%]
       # PERCLOS-driven Tired
       level = "Tired"
       score = 25 + int((perclos - PERCLOS_AWAKE_MAX)
                        / (PERCLOS_TIRED_MAX - PERCLOS_AWAKE_MAX) * 25)
       confidence = 0.3 + (perclos - PERCLOS_AWAKE_MAX) \
                        / (PERCLOS_TIRED_MAX - PERCLOS_AWAKE_MAX) * 0.3

   elif yawn_count >= YAWN_COUNT_THRESHOLD:
       # Yawn-driven Tired (PERCLOS có thể thấp nhưng đang ngáp nhiều)
       level = "Tired"
       score = 35  # midpoint của Tired range (26-50)
       confidence = min(0.80, yawn_count / (YAWN_COUNT_THRESHOLD * 2))

   ═══════════════════════════════════════════════════════════════
   CHECK 4 — Awake: mặc định (PERCLOS ≤ 15%, không có dấu hiệu phụ)
   ═══════════════════════════════════════════════════════════════

   else:
       level = "Awake"
       score = int(perclos / PERCLOS_AWAKE_MAX * 25)  # nội suy 0→15% → 0→25
       confidence = 0.7 + (1.0 - perclos / PERCLOS_AWAKE_MAX) * 0.3

4. Trả về ClassificationResult:
   ClassificationResult(
       fatigue_score=score,
       fatigue_level=level,
       confidence=round(confidence, 4),
       classification_method="rule_based",
       features={
           "ear": fv.ear_avg, "perclos": fv.perclos, "mar": fv.mar,
           "yaw": fv.yaw, "pitch": fv.pitch, "roll": fv.roll,
       }
   )
```

**Lưu ý về logic OR**:
- Mỗi CHECK kiểm tra điều kiện PERCLOS **HOẶC** điều kiện phụ (không yêu cầu cả 2 cùng đúng). Ví dụ: head-tilt ≥ 3s kích hoạt Drowsy kể cả khi PERCLOS = 5%.
- Khi được kích hoạt bởi PERCLOS → score nội suy từ PERCLOS. Khi được kích hoạt bởi điều kiện phụ → score dùng giá trị midpoint của khoảng (60 cho Drowsy, 35 cho Tired).
- Thứ tự kiểm tra: microsleep trước PERCLOS trong cùng mức Dangerous — nếu cả 2 cùng đúng, microsleep được ưu tiên (score=100, confidence cao hơn).

#### Khi không có mặt (`face_detected == False`)

`FeatureVector` toàn 0.0 → `perclos=0.0`, `ear_avg=0.0`, `mar=0.0`:
- `fatigue_level = "Unknown"`
- `fatigue_score = -1`
- `confidence = 0.0`
- `features = {all: 0.0}`

### 4. Tích hợp với FatigueDetector

#### Constructor thay đổi

```python
class FatigueDetector:
    def __init__(
        self,
        landmark_service: FaceLandmarkerService,
        feature_service: FeatureService,
        classifier: IClassifier,            # ← THÊM
    ) -> None: ...
```

#### `_run_inference()` thay đổi

```python
def _run_inference(self, frame, frame_id, frame_timestamp) -> dict:
    timestamp_ms = int(time.time() * 1000)
    lm_result = self._landmark_service.detect(frame, timestamp_ms)

    if not lm_result.face_detected or lm_result.landmarks is None:
        self._feature_service.extract(lm_result, timestamp_ms)
        return self._build_result(frame_id, frame_timestamp,
            fatigue_score=-1, fatigue_level="Unknown",
            confidence=0.0, classification_method=self._classifier.method,
            features={...all zeros...})

    fv = self._feature_service.extract(lm_result, timestamp_ms)
    cr = self._classifier.classify(fv)

    return self._build_result(frame_id, frame_timestamp,
        fatigue_score=cr.fatigue_score,
        fatigue_level=cr.fatigue_level,
        confidence=cr.confidence,
        classification_method=cr.classification_method,
        features=cr.features)
```

#### Loại bỏ code cũ

Xóa các thuộc tính không còn dùng:
- `self._ear_history: list[float]`
- `self._closed_eye_frames: int`
- `self._ear_threshold`, `self._drowsy_frames`, `self._sliding_window_size` (logic chuyển vào `RuleBasedClassifier`)

### 5. Output Schema (RabbitMQ `driver.result`)

```json
{
  "frame_id": 1234,
  "timestamp": 1712345678.123,
  "fatigue_score": 45,
  "fatigue_level": "Tired",
  "confidence": 0.85,
  "classification_method": "rule_based",
  "features": {
    "ear": 0.18,
    "perclos": 22.5,
    "mar": 0.15,
    "yaw": -5.2,
    "pitch": 3.1,
    "roll": 1.8
  }
}
```

### 6. Cấu hình mới trong `core/config.py`

```python
# ── Rule-based classifier thresholds ──
PERCLOS_AWAKE_MAX: float = float(os.getenv("PERCLOS_AWAKE_MAX", "15.0"))
PERCLOS_TIRED_MAX: float = float(os.getenv("PERCLOS_TIRED_MAX", "25.0"))
PERCLOS_DROWSY_MAX: float = float(os.getenv("PERCLOS_DROWSY_MAX", "40.0"))
YAWN_COUNT_THRESHOLD: int = int(os.getenv("YAWN_COUNT_THRESHOLD", "3"))
YAWN_WINDOW_SECONDS: int = int(os.getenv("YAWN_WINDOW_SECONDS", "60"))
HEAD_TILT_DURATION_SECONDS: float = float(os.getenv("HEAD_TILT_DURATION_SECONDS", "3.0"))
MICROSLEEP_DURATION_SECONDS: float = float(os.getenv("MICROSLEEP_DURATION_SECONDS", "2.0"))
```

### Tích hợp với Layered Architecture

```
api/                         ← KHÔNG thay đổi
    └── fatigue.py

services/                    ← Business logic layer
    ├── classifier_interface.py      ← TẠO MỚI: IClassifier ABC
    ├── rule_based_classifier.py     ← TẠO MỚI: RuleBasedClassifier
    ├── feature_service.py           ← ĐÃ CÓ, giữ nguyên
    ├── feature_engineering.py       ← ĐÃ CÓ, giữ nguyên
    ├── mediapipe_service.py         ← ĐÃ CÓ, giữ nguyên
    └── fatigue_detector.py          ← SỬA: nhận classifier, gọi classify()

schemas/
    └── classification_result.py     ← TẠO MỚI: ClassificationResult dataclass

core/
    └── config.py                    ← SỬA: thêm 7 threshold rule-based

messaging/
    ├── orchestrator.py              ← SỬA: wire RuleBasedClassifier
    └── consumer.py                  ← SỬA: publish schema mới
```

Quy tắc phụ thuộc đảm bảo:
- `rule_based_classifier.py` → import từ `feature_service` (type), `schemas` (result), `core/config` (thresholds)
- `fatigue_detector.py` → import `IClassifier` (abstract), không import `RuleBasedClassifier` trực tiếp (DIP)
- `orchestrator.py` → import `RuleBasedClassifier` (concrete), inject vào `FatigueDetector`

### Độ phức tạp & latency estimate

| Thành phần | Thời gian/frame | Ghi chú |
|---|---|---|
| `RuleBasedClassifier.classify()` | **~0.005ms** | Vài phép so sánh + dict tạo. Hoàn toàn không đáng kể. |

## API Contract

**Không thêm API mới.** `GET /health` và `GET /stats` giữ nguyên. `GET /stats` được cập nhật thêm:
- `classification_method`: `"rule_based"` (hoặc `"random_forest"` sau này)
- `fatigue_level_distribution`: `{"Awake": N, "Tired": N, "Drowsy": N, "Dangerous": N, "Unknown": N}`

## Rủi ro & câu hỏi mở

| Rủi ro | Mức độ | Giảm thiểu |
|---|---|---|
| **Rule-based kém chính xác hơn ML** | Thấp | Đây là fallback / bước trung gian. Sẽ được thay thế bởi RF classifier ở FEAT-rf-integration. |
| **Timestamp dùng cho microsleep/head tilt** | Thấp | Dùng `time.time()` monotonic. Sai lệch vài ms không ảnh hưởng ngưỡng 2-3 giây. |
| **State không persistent** | Thấp | Microsleep/head-tilt state reset khi restart service. Chấp nhận được — restart là sự kiện hiếm. |

Không có câu hỏi mở — mọi quyết định đã được chốt.

## Ảnh hưởng tới service khác

- **camera-service**: Không ảnh hưởng.
- **frontend / consumer khác**: Cần cập nhật parser cho schema `driver.result` mới (thêm `fatigue_score`, `fatigue_level`, `classification_method`, `features`).

## Trạng thái xác nhận

`[x] Đã xác nhận bởi người dùng ngày 2026-07-11`
