# TS-remove-headpose: Loại bỏ Head Pose khỏi toàn bộ Pipeline Drowsiness Detection

## Thuộc Feature
- `.opencode/knowledge/features/FEAT-remove-headpose-drowsiness-level.md`
- `.opencode/knowledge/features/FEAT-remove-headpose-rule-engine.md`
- `.opencode/knowledge/features/FEAT-remove-headpose-detector.md`
- `.opencode/knowledge/features/FEAT-remove-headpose-utils-config.md`

## Kiến trúc

### Pipeline sau refactor (chỉ còn Pipeline A — DrowsinessDetector)

```
Frame (BGR ndarray)
    │
    ▼
FaceLandmarker.detect_all()          # YOLO-Face → crop → MediaPipe → list[list[(x,y)]]
    │
    ▼
DriverSelector.select()              # Chọn khuôn mặt tài xế từ multi-face
    │
    ▼
EyeCropper.crop_left() / crop_right()
MouthCropper.crop()                  # Crop ROI từ landmarks
    │
    ├── crop_valid = True (cả 3 ROI khác None)
    │       │
    │       ▼
    │   Predictor.predict()           # Eye CNN + Mouth CNN
    │       │
    │       ▼
    │   GeometricVerifier             # EAR/MAR second opinion
    │       │
    │       ▼
    │   combine_eye_signal()          # CNN OR Geometric → OPEN/CLOSED
    │   combine_mouth_signal()        # CNN OR Geometric → YAWN/NO_YAWN
    │       │
    │       ▼
    │   EyeStateBuffer.update()       # PERCLOS + microsleep detection
    │   MouthStateBuffer.update()     # Yawn vs talking filter
    │       │
    │       ▼
    │   DrowsinessRuleEngine.decide(
    │       face_detected=True,
    │       crop_valid=True,
    │       eye_buffer_result,
    │       mouth_buffer_result,
    │   ) → NORMAL | DROWSY
    │
    └── crop_valid = False (thiếu ≥1 ROI)
            │
            ▼
        DrowsinessRuleEngine.decide(
            face_detected=True,
            crop_valid=False,
            eye_buffer_result=None,
            mouth_buffer_result=None,
        ) → FACE_DETECTED_BUT_INVALID
```

### Kiến trúc file — Layered Architecture (không thay đổi)

```
app/
├── models/
│   └── drowsiness_level.py          # [SỬA] DrowsinessLevel enum, LEVEL_DISPLAY
├── services/
│   ├── decision/
│   │   └── drowsiness_rule_engine.py # [SỬA] decide() interface + logic
│   ├── drowsiness_detector.py        # [SỬA] Pipeline, overlay, process()
│   ├── feature_service.py            # [SỬA] Bỏ import headpose, hardcode 0
│   └── fatigue_detector.py           # [SỬA] Bỏ yaw/pitch/roll khỏi _EMPTY_FEATURES
├── utils/
│   └── headpose.py                   # [XÓA] Toàn bộ file
├── core/
│   ├── config.py                     # [SỬA] Xóa HEAD_POSE_* thresholds
│   └── drowsiness_config.py          # [SỬA] Xóa yaw/pitch_threshold_deg
tests/
└── test_fatigue.py                   # [SỬA] Xóa "yaw","pitch","roll" khỏi test data
```

## Logic + AI

### Thuật toán (không thay đổi phần AI hiện có)
- **Eye CNN** (`EyeClassifier`): MobileNet-style CNN, input 64x64 grayscale eye ROI, output OPEN/CLOSED + probability.
- **Mouth CNN** (`MouthClassifier`): MobileNet-style CNN, input 64x64 grayscale mouth ROI, output YAWN/NO_YAWN + probability.
- **Geometric Verifier**: EAR (Eye Aspect Ratio) với threshold 0.21, MAR (Mouth Aspect Ratio) với threshold 0.6.
- **EyeStateBuffer**: PERCLOS sliding window 3.0s, microsleep threshold 1.5s.
- **MouthStateBuffer**: Yawn filter 4.0s window, min yawn duration 1.5s, talking transition threshold 3.

### Phần bị LOẠI BỎ
- `extract_head_pose()` — decomposition 4×4 rotation matrix → Euler angles (yaw/pitch/roll).
- Toàn bộ logic liên quan đến head pose threshold, looking away detection.

### Ngưỡng (threshold) — không thay đổi
- `EAR_THRESHOLD`: 0.22 (config.py)
- `MAR_THRESHOLD`: 0.6 (config.py)
- `PERCLOS_WINDOW_SECONDS`: 30 (config.py)
- `eye_window_seconds`: 3.0 (drowsiness_config.py)
- `perclos_drowsy_threshold`: 0.5 (drowsiness_config.py)
- `microsleep_seconds`: 1.5 (drowsiness_config.py)
- `mouth_window_seconds`: 4.0 (drowsiness_config.py)
- `yawn_min_duration`: 1.5 (drowsiness_config.py)

### Độ phức tạp
- Loại bỏ Head Pose **giảm** computation: không cần decomposition ma trận 4×4 mỗi frame.
- Không ảnh hưởng đến Eye/Mouth CNN inference (vẫn chạy như cũ).
- Ước tính tiết kiệm ~0.1-0.2ms/frame (không đáng kể so với CNN inference ~5-10ms).

## API Contract

### Không thay đổi API public
```
GET /health    → { "status": "healthy"|"degraded", "service": "driver-service", ... }
GET /stats     → { "uptime": ..., "total_frames": ..., "avg_inference_ms": ..., ... }
GET /frame     → image/jpeg (debug)
```

### DrowsinessDetector.process() — internal API (dùng bởi SafetyMonitor + demos)

**Input** (không đổi):
```python
def process(self, frame: np.ndarray, timestamp: float | None = None) -> tuple[np.ndarray, dict]:
```

**Output** (thay đổi `level` field):
```python
(
    frame_with_overlay: np.ndarray,  # BGR image with overlay drawn
    {
        "level": DrowsinessLevel,     # NORMAL | DROWSY | NO_FACE | FACE_DETECTED_BUT_INVALID
        "eye": dict | None,
        "mouth": dict | None,
        "eye_buffer": dict | None,
        "mouth_buffer": dict | None,
    }
)
```

### DrowsinessRuleEngine.decide() — internal API

**Input mới**:
```python
def decide(
    self,
    face_detected: bool,
    crop_valid: bool,
    eye_buffer_result: dict | None,
    mouth_buffer_result: dict | None,
) -> DrowsinessLevel:
```

**Output**: `DrowsinessLevel` (1 trong 4 giá trị).

## Chi tiết thay đổi từng file

### 1. `app/models/drowsiness_level.py`

**Enum mới**:
```python
class DrowsinessLevel(str, Enum):
    NORMAL = "NORMAL"
    DROWSY = "DROWSY"
    NO_FACE = "NO_FACE"
    FACE_DETECTED_BUT_INVALID = "FACE_DETECTED_BUT_INVALID"
```

**LEVEL_DISPLAY mới**:
```python
LEVEL_DISPLAY: dict[DrowsinessLevel, dict] = {
    DrowsinessLevel.NORMAL: {"text": "AWAKE", "color": (0, 255, 0)},
    DrowsinessLevel.DROWSY: {"text": "DROWSY - WAKE UP!", "color": (0, 0, 255)},
    DrowsinessLevel.NO_FACE: {"text": "NO FACE DETECTED", "color": (0, 0, 255)},
    DrowsinessLevel.FACE_DETECTED_BUT_INVALID: {"text": "FACE DETECTED (INVALID)", "color": (0, 165, 255)},
}
```

### 2. `app/services/decision/drowsiness_rule_engine.py`

**Signature mới**:
```python
def decide(
    self,
    face_detected: bool,
    crop_valid: bool,
    eye_buffer_result: dict | None,
    mouth_buffer_result: dict | None,
) -> DrowsinessLevel:
```

**Logic mới**:
```python
if not face_detected:
    return DrowsinessLevel.NO_FACE

if not crop_valid:
    return DrowsinessLevel.FACE_DETECTED_BUT_INVALID

if eye_buffer_result is not None and eye_buffer_result.get("is_microsleep"):
    return DrowsinessLevel.DROWSY

if eye_buffer_result is not None and eye_buffer_result.get("is_perclos_drowsy"):
    return DrowsinessLevel.DROWSY

if mouth_buffer_result is not None and mouth_buffer_result.get("is_real_yawn"):
    return DrowsinessLevel.DROWSY

return DrowsinessLevel.NORMAL
```

### 3. `app/services/drowsiness_detector.py`

**Docstring**: Cập nhật pipeline diagram (bỏ "Head Pose Check").

**`_draw_overlay()` method**: 
- Xóa `pose_result: dict` parameter.
- Xóa block hiển thị Yaw/Pitch (dòng 128-131).
- Đổi `DrowsinessLevel.DROWSY_SEVERE` → `DrowsinessLevel.DROWSY` cho warning border.

**`process()` method**:
- Tính `face_detected = landmarks is not None`
- Tính `crop_valid = (left_eye_roi is not None and right_eye_roi is not None and mouth_roi is not None)`
- Gọi `self.rule_engine.decide(face_detected, crop_valid, eye_buffer_result, mouth_buffer_result)`
- Khi `crop_valid=False`, `eye_buffer_result` và `mouth_buffer_result` là `None`.
- Khi `face_detected=False` (landmarks=None), gọi `decide(False, False, None, None)`.

### 4. `app/utils/headpose.py`

**XÓA TOÀN BỘ FILE**.

### 5. `app/core/drowsiness_config.py`

Xóa 2 field:
```python
yaw_threshold_deg: float = 30.0      # XÓA
pitch_threshold_deg: float = 25.0    # XÓA
```

### 6. `app/core/config.py`

Xóa 2 dòng:
```python
HEAD_POSE_PITCH_THRESHOLD: float = float(os.getenv("HEAD_POSE_PITCH_THRESHOLD", "20.0"))
HEAD_POSE_YAW_THRESHOLD: float = float(os.getenv("HEAD_POSE_YAW_THRESHOLD", "25.0"))
```

### 7. `app/services/feature_service.py`

- Xóa `from app.utils.headpose import extract_head_pose`.
- Trong `extract()`: thay vì gọi `extract_head_pose(result.transformation_matrix)`, hardcode `yaw, pitch, roll = 0.0, 0.0, 0.0`.
- Giữ nguyên `roots` dict với `"yaw": 0.0, "pitch": 0.0, "roll": 0.0`.
- Giữ nguyên `_NEUTRAL_ROOTS` với `"yaw": 0.0, "pitch": 0.0, "roll": 0.0`.

### 8. `app/services/fatigue_detector.py`

Sửa `_EMPTY_FEATURES`:
```python
# Before:
_EMPTY_FEATURES: dict[str, float] = {
    "ear": 0.0, "perclos": 0.0, "mar": 0.0,
    "yaw": 0.0, "pitch": 0.0, "roll": 0.0,
}

# After:
_EMPTY_FEATURES: dict[str, float] = {
    "ear": 0.0, "perclos": 0.0, "mar": 0.0,
}
```

### 9. `tests/test_fatigue.py`

Sửa dòng 98-99:
```python
# Before:
features={"ear": 0.2, "perclos": 20.0, "mar": 0.1,
           "yaw": 0.0, "pitch": 0.0, "roll": 0.0},

# After:
features={"ear": 0.2, "perclos": 20.0, "mar": 0.1},
```

### 10. `app/services/mediapipe_service.py`

Cập nhật comment ở docstring (dòng 8-9) và field docstring (dòng 61-65) — xóa reference đến Head Pose, giữ nguyên mô tả về transformation_matrix (vẫn extract từ MediaPipe, nhưng downstream không dùng). **Hoặc**: set `output_facial_transformation_matrixes=False` trong options để MediaPipe không compute matrix (tiết kiệm computation), và xóa field `transformation_matrix` khỏi `FaceLandmarkerResult`. Tuy nhiên vì `feature_service.py` vẫn reference `result.transformation_matrix`, nên giữ nguyên để tránh break.

**Quyết định**: Giữ nguyên `FaceLandmarkerResult` và `FaceLandmarkerService` — không sửa code, chỉ cập nhật comment. Không set `output_facial_transformation_matrixes=False` vì có thể ảnh hưởng đến hành vi MediaPipe không lường trước.

### Các file KHÔNG sửa

| File | Lý do |
|------|-------|
| `app/services/eye_cropper.py` | Không liên quan đến head pose |
| `app/services/mouth_cropper.py` | Không liên quan đến head pose |
| `app/services/classifiers/predictor.py` | Không liên quan đến head pose |
| `app/services/classifiers/eye_classifier.py` | Không liên quan |
| `app/services/classifiers/mouth_classifier.py` | Không liên quan |
| `app/services/geometric_verifier.py` | Không liên quan đến head pose |
| `app/services/driver_selector.py` | Không liên quan đến head pose |
| `app/services/temporal/eye_state_buffer.py` | Không liên quan |
| `app/services/temporal/mouth_state_buffer.py` | Không liên quan |
| `app/services/safety_monitor.py` | Chỉ gọi `drowsiness_detector.process()`, không touch head pose |
| `app/services/seatbelt_detector.py` | Không liên quan |
| `app/services/feature_engineering.py` | Buffer vẫn compile với giá trị 0.0 (không cần sửa) |
| `app/services/face_landmarker.py` | Chỉ có comment reference, không cần sửa code |
| `app/demo/run_webcam.py` | Dùng FaceLandmarker + EyeCropper + MouthCropper + Predictor trực tiếp, không dùng DrowsinessDetector |
| `app/demo/run_image.py` | Chỉ dùng FaceLandmarker + crop, không liên quan |
| `app/demo/run_webcam_with_controls.py` | Dùng SafetyMonitor → DrowsinessDetector, nhưng không touch head pose trực tiếp |
| `app/demo/run_video_with_controls.py` | Tương tự |
| `app/demo/run_video.py` | Tương tự |
| `app/api/fatigue.py` | API endpoints không thay đổi |
| `app/messaging/orchestrator.py` | Tiếp tục dùng FatigueDetector (pipeline B), không bị ảnh hưởng vì feature_service.py vẫn compile |
| `app/main.py` | Không thay đổi |

## Rủi ro & câu hỏi mở

- **Đã giải quyết**: Pipeline B (FatigueDetector) — user xác nhận không dùng RF, chỉ dùng Pipeline A. `feature_service.py` được giữ compile bằng cách hardcode yaw/pitch/roll = 0.0.
- **Rủi ro thấp**: `FaceLandmarkerResult.transformation_matrix` vẫn được extract từ MediaPipe nhưng không còn ai dùng. Không gây lỗi, chỉ lãng phí nhẹ computation (~microseconds). Có thể tối ưu sau nếu cần.
- **Rủi ro thấp**: `FeatureVector` 40-field vẫn giữ nguyên 15 field head-pose = 0.0. RF model nếu được load sẽ nhận input 40 chiều nhưng head-pose feature = 0 — có thể cho kết quả không chính xác. Tuy nhiên user đã xác nhận không dùng RF.

## Ảnh hưởng tới service khác
Không ảnh hưởng. Chỉ thay đổi trong `driver-service`.

## Trạng thái xác nhận
`[x] Đã xác nhận bởi người dùng ngày 2026-07-15 — ĐÃ IMPLEMENT`
