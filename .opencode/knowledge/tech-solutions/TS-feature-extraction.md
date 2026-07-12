# TS-feature-extraction: MAR, HeadPose, PERCLOS + Full 40-Feature Engineering

> **Hợp thức hóa ngày 2026-07-11**: Tài liệu này được viết lại để **khớp chính xác code thật** đã implement trong `driver-service/app/`. Đây không phải thiết kế mới — đây là documentation của code hiện hữu.

## Thuộc Feature
`.opencode/knowledge/features/FEAT-feature-extraction.md`

## Kiến trúc

### Tổng quan

Toàn bộ pipeline feature extraction từ `FaceLandmarkerResult` → 40-feature vector, đồng nhất giữa runtime (driver-service) và offline training (training scripts) thông qua 1 module dùng chung: `app/services/feature_engineering.py`.

**Phạm vi**: driver-service ONLY.

**Nguyên tắc then chốt**:
- **1 module dùng chung**: `WindowedFeatureEngineer` trong `services/feature_engineering.py` được import bởi CẢ `FeatureService` (runtime) và `training/engineer_features.py` (offline). KHÔNG viết 2 bản logic riêng.
- Pure function cho per-frame math: `utils/mar.py`, `utils/headpose.py` (không I/O, không state).
- Stateful class cho sliding window: `services/feature_engineering.py` (quản lý deque buffers).
- `FeatureService` = orchestrator: nhận `FaceLandmarkerResult` → gọi `FeatureEngineer` → trả `FeatureVector`.

```
app/
├── utils/
│   ├── ear.py                    # ĐÃ CÓ — pure function calculate_ear()
│   ├── mar.py                    # ĐÃ CÓ — pure function calculate_mar()
│   └── headpose.py               # ĐÃ CÓ — pure function extract_head_pose()
├── services/
│   ├── mediapipe_service.py      # ĐÃ CÓ — FaceLandmarkerService + FaceLandmarkerResult
│   ├── feature_engineering.py    # ĐÃ CÓ — WindowedFeatureEngineer (DÙNG CHUNG)
│   ├── feature_service.py        # ĐÃ CÓ — FeatureService (orchestrator) + FeatureVector
│   └── fatigue_detector.py       # ĐÃ SỬA — gọi FeatureService.extract(), giữ EAR classification
├── core/
│   └── config.py                 # ĐÃ SỬA — thêm 8 cấu hình feature extraction
└── main.py                       # KHÔNG SỬA — DI wiring qua MessagingOrchestrator
```

### Luồng dữ liệu (runtime)

```
FaceLandmarkerResult (từ FaceLandmarkerService.detect())
    │
    ├── .landmarks (478) ────────────────┐
    ├── .face_detected (bool)            │
    └── .transformation_matrix (4×4) ───┐│
                                         ││
    ┌────────────────────────────────────┘│
    │                                     │
    ▼                                     ▼
┌───────────────────────────────┐  ┌────────────────────────────┐
│ utils/ear.py                  │  │ utils/headpose.py          │
│ calculate_ear() × 2           │  │ extract_head_pose(mat)     │
│  → EAR_left, EAR_right        │  │  → (yaw, pitch, roll)°     │
├───────────────────────────────┤  └────────────────────────────┘
│ utils/mar.py                  │
│ calculate_mar()               │
│  → MAR                        │
└───────────────┬───────────────┘
                │
                ▼  7 root features: {ear_left, ear_right, ear_avg, mar, yaw, pitch, roll}
                │
    ┌───────────┴──────────────────────────────────────────────────┐
    │ services/feature_engineering.py  (DÙNG CHUNG runtime+train)  │
    │ WindowedFeatureEngineer.update(roots) → dict[str, float]     │
    │                                                              │
    │  ┌─────────────────────────────────────────────────────────┐ │
    │  │ 7 SlidingWindowBuffer (N_STAT=300) → 28 stats           │ │
    │  │   {F}_mean, {F}_std, {F}_min, {F}_max                   │ │
    │  ├─────────────────────────────────────────────────────────┤ │
    │  │ PERCLOS buffer (N_PERCLOS=900) → perclos, blink_rate    │ │
    │  ├─────────────────────────────────────────────────────────┤ │
    │  │ Velocity buffers (N_VEL=30) → yaw/pitch/roll_velocity   │ │
    │  └─────────────────────────────────────────────────────────┘ │
    └──────────────────────────┬───────────────────────────────────┘
                               │ dict[str, float] (40 keys)
                               ▼
    ┌──────────────────────────────────────────────────────────────┐
    │ services/feature_service.py                                  │
    │ FeatureService.extract(landmarker_result, timestamp_ms)      │
    │  1. Gọi utils để lấy 7 root features                         │
    │  2. Gọi WindowedFeatureEngineer.update(roots) → dict         │
    │  3. FeatureVector(**fv_dict) → trả về FeatureVector          │
    └──────────────────────────┬───────────────────────────────────┘
                               │ FeatureVector
                               ▼
                      FatigueDetector.process()
                      → fv.ear_avg → EAR sliding window → sleepy bool
                      → RabbitMQ publish
```

### Khác biệt Runtime vs Training

| Khía cạnh | Runtime (`FeatureService`) | Training (`engineer_features.py`) |
|---|---|---|
| **Số luồng dữ liệu** | 1 luồng frame liên tục (không có nhóm) | Nhiều nhóm (subject_id, scenario) riêng biệt |
| **Window reset** | Reset khi service khởi động lại (state rỗng tự nhiên). KHÔNG có logic reset theo nhóm. | Reset khi chuyển sang nhóm mới — tạo `WindowedFeatureEngineer` mới cho mỗi nhóm. |
| **Cold-start** | Expanding window: frame đầu dùng toàn bộ dữ liệu có sẵn (cửa sổ nhỏ hơn). PERCLOS từ từ hội tụ khi window đầy. | **KHÔNG** expanding window: frame có `perclos_depth < 900` bị LOẠI BỎ (theo TS-dataset-training.md Step 3d). |
| **Dùng chung code** | `from app.services.feature_engineering import WindowedFeatureEngineer` | `from app.services.feature_engineering import WindowedFeatureEngineer` — CÙNG 1 import |

### File hiện trạng

| File | Trạng thái | Ghi chú |
|---|---|---|
| `app/utils/mar.py` | ✅ ĐÃ IMPLEMENT | `calculate_mar(landmarks) -> float`. Inner-lip MAR (indices 13, 14, 61, 291). Outer-lip variant reserved. |
| `app/utils/headpose.py` | ✅ ĐÃ IMPLEMENT | `extract_head_pose(transformation_matrix) -> tuple[float, float, float]`. Decompose rotation matrix → Euler angles. Gimbal-lock handling. |
| `app/services/feature_engineering.py` | ✅ ĐÃ IMPLEMENT | `SlidingWindowBuffer` + `WindowedFeatureEngineer`. 219 dòng. |
| `app/services/feature_service.py` | ✅ ĐÃ IMPLEMENT | `FeatureVector` (40-field dataclass) + `FeatureService` (orchestrator). 196 dòng. |
| `app/core/config.py` | ✅ ĐÃ SỬA | Thêm 8 cấu hình: `MAR_THRESHOLD`, `PERCLOS_WINDOW_SECONDS`, `HEAD_POSE_PITCH_THRESHOLD`, `HEAD_POSE_YAW_THRESHOLD`, `FPS_ASSUMPTION`, `N_STAT`, `N_PERCLOS`, `N_VEL`. |
| `app/services/fatigue_detector.py` | ✅ ĐÃ SỬA | Constructor nhận `feature_service: FeatureService`. `_run_inference()` gọi `feature_service.extract()` lấy `FeatureVector`, dùng `fv.ear_avg` cho EAR sliding window classification (vẫn giữ logic cũ `_ear_history` + `_closed_eye_frames`). |

## Logic + AI

### 1. SlidingWindowBuffer (`services/feature_engineering.py`)

Wrapper quản lý 1 deque cho 1 feature series. **Frame-based** (ADR-005): đếm theo số frame, không theo timestamp.

```python
@dataclass
class SlidingWindowBuffer:
    max_size: int            # e.g., 300, 900, 30
    _buffer: deque[float]    # internal, auto-pop oldest when full

    def push(self, value: float) -> None   # append; auto-popleft if > max_size
    def values(self) -> list[float]         # snapshot (oldest → newest)
    def depth(self) -> int                  # current len
    def is_full(self) -> bool               # depth >= max_size
    def reset(self) -> None                 # clear all (training use)
```

**ADR-005**: `deque[float]`, `max_size = window_seconds × FPS_ASSUMPTION`. Mỗi `push()` = 1 frame. KHÔNG lưu timestamp. O(1) mọi thao tác.

### 2. WindowedFeatureEngineer (`services/feature_engineering.py`)

#### Constructor (khớp code thật)

```python
class WindowedFeatureEngineer:
    def __init__(
        self,
        n_stat: int = 300,
        n_perclos: int = 900,
        n_vel: int = 30,
        ear_threshold: float = 0.22,
        fps: int = 30,
    ) -> None:
```

> ⚠️ **Khác với thiết kế ban đầu**: Constructor nhận **từng tham số riêng lẻ** (int/float), không nhận `Settings` object. Lý do: để training script có thể tạo instance mà không cần mock toàn bộ Settings.

#### Internal buffers (11 total)

| Buffer | Window size | Chứa giá trị | Mục đích |
|---|---|---|---|
| `_ear_left_buf` | 300 (10s) | `ear_left` | 4 stats |
| `_ear_right_buf` | 300 (10s) | `ear_right` | 4 stats |
| `_ear_avg_buf` | 300 (10s) | `ear_avg` | 4 stats |
| `_mar_buf` | 300 (10s) | `mar` | 4 stats |
| `_yaw_buf` | 300 (10s) | `yaw` | 4 stats |
| `_pitch_buf` | 300 (10s) | `pitch` | 4 stats |
| `_roll_buf` | 300 (10s) | `roll` | 4 stats |
| `_perclos_buf` | 900 (30s) | `ear_avg` | PERCLOS + blink_rate |
| `_yaw_vel_buf` | 30 (1s) | `yaw` | yaw_velocity |
| `_pitch_vel_buf` | 30 (1s) | `pitch` | pitch_velocity |
| `_roll_vel_buf` | 30 (1s) | `roll` | roll_velocity |

7 stat buffers được gom vào `self._stat_buffers: list[tuple[SlidingWindowBuffer, str]]` để iteration DRY.

#### `update(roots: dict[str, float]) -> dict[str, float]`

Nhận dict 7 root features, trả về dict 40 keys. **Không trả về `FeatureVector`** — `FeatureVector` do `FeatureService` tạo từ dict này.

Thứ tự tính trong code (khớp chính xác):

```
A. Copy 7 root features trực tiếp vào output dict
B. 28 statistical features: với mỗi buffer trong _stat_buffers, tính
   np.mean, np.std(ddof=1), np.min, np.max trên toàn bộ buffer.values
C. PERCLOS: count(ear_avg < EAR_THRESHOLD) / len(perclos_buf) * 100
D. Blink rate: _compute_blink_rate() — đếm blink onset (crossing below threshold),
   debounce 5 frame giữa 2 blink liên tiếp, đơn vị blinks/phút
E. 3 velocities: _mean_abs_diff() — np.mean(np.abs(np.diff(values))) * 30
   (FPS hardcoded 30, không dùng self._fps)
```

#### Cold-start behavior (expanding window)

Buffer chưa đầy → `buf.values` trả về toàn bộ phần tử hiện có. PERCLOS = tỉ lệ trên dữ liệu thấy được. Khi buffer đầy → kết quả ổn định.

### 3. FeatureVector (`services/feature_service.py`)

`@dataclass` 40 field. Thứ tự field **phải khớp chính xác** thứ tự cột trong CSV training để `model.predict(array)` nhận đúng input:

```python
@dataclass
class FeatureVector:
    # ── A. Root features (7) ──
    ear_left: float = 0.0       #  1
    ear_right: float = 0.0      #  2
    ear_avg: float = 0.0        #  3
    mar: float = 0.0            #  4
    yaw: float = 0.0            #  5
    pitch: float = 0.0          #  6
    roll: float = 0.0           #  7

    # ── B. Sliding window statistics (28) — N=300 backward ──
    ear_left_mean: float = 0.0  #  8
    ear_left_std: float = 0.0   #  9
    ear_left_min: float = 0.0   # 10
    ear_left_max: float = 0.0   # 11
    ear_right_mean: float = 0.0 # 12
    ear_right_std: float = 0.0  # 13
    ear_right_min: float = 0.0  # 14
    ear_right_max: float = 0.0  # 15
    ear_avg_mean: float = 0.0   # 16
    ear_avg_std: float = 0.0    # 17
    ear_avg_min: float = 0.0    # 18
    ear_avg_max: float = 0.0    # 19
    mar_mean: float = 0.0       # 20
    mar_std: float = 0.0        # 21
    mar_min: float = 0.0        # 22
    mar_max: float = 0.0        # 23
    yaw_mean: float = 0.0       # 24
    yaw_std: float = 0.0        # 25
    yaw_min: float = 0.0        # 26
    yaw_max: float = 0.0        # 27
    pitch_mean: float = 0.0     # 28
    pitch_std: float = 0.0      # 29
    pitch_min: float = 0.0      # 30
    pitch_max: float = 0.0      # 31
    roll_mean: float = 0.0      # 32
    roll_std: float = 0.0       # 33
    roll_min: float = 0.0       # 34
    roll_max: float = 0.0       # 35

    # ── C. Temporal/behavioral (5) — backward window ──
    perclos: float = 0.0        # 36  N=900 (30s)
    blink_rate: float = 0.0     # 37  N=900 (30s)
    yaw_velocity: float = 0.0   # 38  N=30 (1s)
    pitch_velocity: float = 0.0 # 39  N=30 (1s)
    roll_velocity: float = 0.0  # 40  N=30 (1s)

    def to_array(self) -> np.ndarray: ...
    def to_dict(self) -> dict[str, float]: ...
```

Khi `face_detected == False`: tất cả 40 field = `0.0`. **Nhưng** engine vẫn được `update()` với neutral roots (`ear=0.35`) để window không bị gap.

### 4. FeatureService (`services/feature_service.py`)

```python
class FeatureService:
    def __init__(self, engine: WindowedFeatureEngineer): ...

    def extract(
        self, result: FaceLandmarkerResult, timestamp_ms: int
    ) -> FeatureVector:
        # timestamp_ms hiện không dùng (reserved cho timestamp-based variant)
        _ = timestamp_ms

        if not result.face_detected or result.landmarks is None:
            self._engine.update(_NEUTRAL_ROOTS)  # ear=0.35, mar=0, pose=0
            return FeatureVector()  # all zeros

        landmarks = result.landmarks
        ear_left = calculate_ear(landmarks, LEFT_EYE)
        ear_right = calculate_ear(landmarks, RIGHT_EYE)
        ear_avg = (ear_left + ear_right) / 2.0
        mar = calculate_mar(landmarks)

        yaw, pitch, roll = (0.0, 0.0, 0.0)
        if result.transformation_matrix is not None:
            yaw, pitch, roll = extract_head_pose(result.transformation_matrix)

        roots = {"ear_left": ..., "ear_right": ..., "ear_avg": ...,
                 "mar": ..., "yaw": ..., "pitch": ..., "roll": ...}
        fv_dict = self._engine.update(roots)
        return FeatureVector(**fv_dict)
```

Module constant `_NEUTRAL_ROOTS`: `ear=0.35, mar=0.0, yaw/pitch/roll=0.0`.

### 5. Tích hợp với FatigueDetector

`FatigueDetector.__init__` nhận cả `landmark_service` và `feature_service`:

```python
class FatigueDetector:
    def __init__(
        self,
        landmark_service: FaceLandmarkerService,
        feature_service: FeatureService,
    ) -> None: ...
```

`_run_inference()`:
1. Gọi `landmark_service.detect()` → `FaceLandmarkerResult`
2. Nếu không có mặt: gọi `feature_service.extract()` (neutral roots) → return sleepy=False
3. Nếu có mặt: gọi `feature_service.extract()` → `FeatureVector`
4. Lấy `fv.ear_avg` → đẩy vào `_ear_history` sliding window → so sánh với `EAR_THRESHOLD` → `sleepy` bool

> ⚠️ **Ghi chú**: Classification vẫn là EAR-threshold đơn giản (code cũ). 40 features đã được tính nhưng chưa được dùng để classify. Việc dùng 40 features để classify sẽ được làm ở `FEAT-fatigue-classifier` (TS-fatigue-classifier).

### Cấu hình trong `core/config.py` (đã implement)

```python
# ── Feature extraction thresholds ──
MAR_THRESHOLD: float = float(os.getenv("MAR_THRESHOLD", "0.6"))
PERCLOS_WINDOW_SECONDS: int = int(os.getenv("PERCLOS_WINDOW_SECONDS", "30"))
HEAD_POSE_PITCH_THRESHOLD: float = float(os.getenv("HEAD_POSE_PITCH_THRESHOLD", "20.0"))
HEAD_POSE_YAW_THRESHOLD: float = float(os.getenv("HEAD_POSE_YAW_THRESHOLD", "25.0"))
FPS_ASSUMPTION: int = int(os.getenv("FPS_ASSUMPTION", "30"))

# ── Window sizes (frames) ──
N_STAT: int = int(os.getenv("N_STAT", "300"))          # 10s @ 30fps
N_PERCLOS: int = int(os.getenv("N_PERCLOS", "900"))    # 30s @ 30fps
N_VEL: int = int(os.getenv("N_VEL", "30"))             # 1s @ 30fps
```

### Độ phức tạp & latency estimate

| Thành phần | Thời gian/frame | Ghi chú |
|---|---|---|
| `calculate_mar` | ~0.01ms | Vài phép Euclidean distance |
| `extract_head_pose` | ~0.005ms | 3× `atan2` + 1× `sqrt` |
| `WindowedFeatureEngineer.update` | ~0.05ms | 11× `deque.append` + 28× `np.mean/std/min/max` trên array ≤ 900 phần tử |
| `FeatureService.extract` (tổng) | **~0.07ms** | So với MediaPipe inference ~15ms → **không đáng kể** (< 0.5%) |

## API Contract

**Không thêm API mới.** Feature này là internal, không expose HTTP endpoint mới.

## Rủi ro & câu hỏi mở

| Rủi ro | Mức độ | Giảm thiểu |
|---|---|---|
| **MAR indices sai** | Thấp | Indices từ MediaPipe Face Landmarker doc, đã unit test |
| **HeadPose Euler angles sai dấu** | Thấp | Đã xử lý gimbal-lock, test với matrix identity |
| **Lệch công thức runtime vs training** | **Cao** → Thấp | DÙNG CHUNG `WindowedFeatureEngineer`. Cùng 1 import. |
| **PERCLOS cold-start expanding window** | Thấp | PERCLOS hội tụ sau 30 giây đầu tiên |
| **40 feature × 11 buffers memory** | Thấp | 11 deque × 900 × 8 bytes ≈ 79KB |
| **`_mean_abs_diff` hardcode `* 30`** | Thấp | Khớp `FPS_ASSUMPTION=30`. Nếu FPS thay đổi → cần sửa cả 2 nơi. |

Không có câu hỏi mở — mọi quyết định đã được chốt.

## Ảnh hưởng tới service khác

**Không ảnh hưởng.** Toàn bộ thay đổi nằm trong `driver-service/`.

## Trạng thái xác nhận

`[x] Đã xác nhận bởi người dùng ngày 2026-07-11` — hợp thức hóa code đã implement.
