# TS-highlevel-model-test: High-level evaluation test cho 4 model

## Thuộc Feature
[FEAT-highlevel-model-test](../features/FEAT-highlevel-model-test.md)

## Kiến trúc

### File tạo mới
```
services/driver-service/tests/
└── test_highlevel_models.py   # File test duy nhất cần tạo
```

**Không sửa** bất kỳ file production nào. Test dùng trực tiếp các class đã có:
- `app/services/face_detector.py::FaceDetector`
- `app/services/face_landmarker.py::FaceLandmarker`
- `app/services/eye_cropper.py::EyeCropper`
- `app/services/mouth_cropper.py::MouthCropper`
- `app/services/classifiers/predictor.py::Predictor`
- `app/services/seatbelt_detector.py::SeatbeltDetector`

### Luồng dữ liệu

```
Dataset (highlevel/*.jpg)
│
├── 1. Parse filename → ground_truth dict
│       {eye, glass, face, yawn, seatbelt}
│
└── 2. For each image:
        │
        ├── cv2.imread() → BGR frame
        │
        ├── FaceDetector.detect(frame)
        │   ├── No bbox → pred_face = "noface"
        │   │             pred_eye = "no_face" (skip)
        │   │             pred_mouth = "no_face" (skip)
        │   │
        │   └── Has bbox → pred_face = "face"
        │                   │
        │                   ├── FaceLandmarker.detect(frame) → landmarks
        │                   │   (reuse FaceDetector instance để tránh load model 2 lần)
        │                   │
        │                   ├── landmarks valid?
        │                   │   ├── YES:
        │                   │   │   EyeCropper → left_eye_roi, right_eye_roi
        │                   │   │   MouthCropper → mouth_roi
        │                   │   │   Predictor.predict(eyes, mouth)
        │                   │   │       → pred_eye: "eyeopen"/"eyeclose"
        │                   │   │       → pred_mouth: "yawn"/"noyawn"
        │                   │   │
        │                   │   └── NO (crop invalid):
        │                   │       pred_eye = "invalid"
        │                   │       pred_mouth = "invalid"
        │                   │
        │                   └── SeatbeltDetector.detect(frame)
        │                       → pred_seatbelt: "seatbelt"/"noseatbelt"
        │
        └── Compare (pred vs gt) → accumulate stats

3. Report:
   ├── Accuracy từng model (%)
   ├── Confusion matrix (text table)
   ├── Eye accuracy breakdown: glass vs noglass
   └── Runtime (giây)
```

### Model path resolution

Dùng `pathlib.Path` relative từ vị trí file test:
```python
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent        # .../tests/
DRIVER_DIR = TEST_DIR.parent                        # .../driver-service/
DATASET_DIR = DRIVER_DIR / "highlevel"
MODEL_DIR = DRIVER_DIR / "app" / "models"

# 4 model paths
FACE_MODEL = MODEL_DIR / "yolov8n-face.pt"         # Face detection
LANDMARK_MODEL = MODEL_DIR / "face_landmarker.task" # MediaPipe landmarks
EYE_MODEL = MODEL_DIR / "eye_state_model.pt"       # Eye CNN
MOUTH_MODEL = MODEL_DIR / "mouth_state_model.pt"   # Mouth CNN
SEATBELT_MODEL = MODEL_DIR / "best.pt"             # Seatbelt YOLO
```

## Logic + AI (nếu có)

### Model 1: Face Detection
| Thuộc tính | Giá trị |
|---|---|
| **Model** | `yolov8n-face.pt` (YOLOv8 nano, face detection) |
| **Class** | `FaceDetector` (`app/services/face_detector.py`) |
| **Input** | BGR frame, shape `(H, W, 3)`, dtype `uint8` |
| **Output** | `list[tuple[int,int,int,int]]` — danh sách bbox `(x1,y1,x2,y2)` pixel |
| **Threshold** | `conf_threshold=0.5` (mặc định FaceDetector) |
| **Ground truth mapping** | Bbox không rỗng → `"face"`, rỗng → `"noface"` |
| **Độ phức tạp** | ~10-20ms/frame (YOLOv8 nano, CPU) |

### Model 2: Eye CNN
| Thuộc tính | Giá trị |
|---|---|
| **Model** | `eye_state_model.pt` (CNN binary classifier) |
| **Class** | `EyeClassifier` → dùng qua `Predictor.predict_eyes()` |
| **Preprocessing** | Resize → ToTensor → ImageNet Normalize (trong `ImagePreprocessor`) |
| **Input** | Left eye ROI + right eye ROI, mỗi cái là `np.ndarray` BGR (crop từ `EyeCropper`) |
| **Output** | `{"label": "OPEN"/"CLOSED", "confidence": float, "probability": float}` |
| **Threshold** | `probability >= 0.5` → OPEN, else CLOSED |
| **Ground truth mapping** | `"OPEN"` → `"eyeopen"`, `"CLOSED"` → `"eyeclose"` |
| **Độ phức tạp** | ~1-2ms cho 2 mắt (CNN nhỏ) |
| **Ghi chú** | Chỉ prediction hợp lệ khi face detected VÀ crop valid |

### Model 3: Mouth CNN
| Thuộc tính | Giá trị |
|---|---|
| **Model** | `mouth_state_model.pt` (CNN binary classifier) |
| **Class** | `MouthClassifier` → dùng qua `Predictor.predict_mouth()` |
| **Preprocessing** | Resize → ToTensor → ImageNet Normalize |
| **Input** | Mouth ROI, `np.ndarray` BGR (crop từ `MouthCropper`) |
| **Output** | `{"label": "YAWN"/"NO_YAWN", "confidence": float, "probability": float}` |
| **Threshold** | `probability >= 0.5` → YAWN, else NO_YAWN |
| **Ground truth mapping** | `"YAWN"` → `"yawn"`, `"NO_YAWN"` → `"noyawn"` |
| **Độ phức tạp** | ~1ms (CNN nhỏ) |
| **Ghi chú** | Khi no face → luôn expect `NO_YAWN` (miệng đóng) |

### Model 4: Seatbelt YOLO
| Thuộc tính | Giá trị |
|---|---|
| **Model** | `best.pt` (YOLOv8m, multi-class object detection) |
| **Class** | `SeatbeltDetector` (`app/services/seatbelt_detector.py`) |
| **Input** | BGR frame, shape `(H, W, 3)`, dtype `uint8` |
| **Output** | `{"has_seatbelt": bool, "seatbelt_confidence": float, "boxes": [...], "detected_labels": [...]}`|
| **Threshold** | `confidence_threshold=0.3` |
| **Ground truth mapping** | `has_seatbelt=True` → `"seatbelt"`, `False` → `"noseatbelt"` |
| **Độ phức tạp** | ~50-80ms/frame (YOLOv8m, CPU) |
| **Ghi chú** | Chạy trên MỌI frame, không phụ thuộc face detection |

### Lưu ý về FaceLandmarker
- `FaceLandmarker` cần CẢ `yolov8n-face.pt` (YOLO face detection) VÀ `face_landmarker.task` (MediaPipe landmarks).
- Để tránh load YOLO face 2 lần, tạo 1 `FaceDetector` instance dùng chung:
  ```python
  face_detector = FaceDetector(str(FACE_MODEL))
  # Dùng face_detector cho face/noface check
  landmarker = FaceLandmarker(
      model_path=str(LANDMARK_MODEL),
      face_detector=face_detector,  # reuse
  )
  ```

## Cấu trúc code test

```python
# tests/test_highlevel_models.py

import time
from collections import defaultdict
from pathlib import Path
import re

import cv2
import numpy as np
import pytest

# --- Ground truth parsing ---
def parse_filename(filename: str) -> dict:
    """Parse 'eyeopen_glass_face_noyawn_seatbelt_0001.jpg' → dict."""
    ...

# --- Model loading (module-level, load 1 lần) ---
@pytest.fixture(scope="module")
def models():
    """Load all 4 models, return dict of loaded components."""
    ...

# --- Main test ---
def test_highlevel_models(models):
    """Main evaluation test."""
    ...
```

## Kế hoạch output

```
===== HIGHLEVEL MODEL EVALUATION =====
Dataset: 1002 images
Models: Face (yolov8n-face), Eye (CNN), Mouth (CNN), Seatbelt (YOLOv8m)
--------------------------------------
[PROGRESS] 100/1002 (10.0%) ...
...
[PROGRESS] 1000/1002 (99.8%) ...
--------------------------------------

--- Face Detection ---
Accuracy:  XX.X% (xxx/1002)
Confusion Matrix:
              Pred
              face  noface
Actual face     XX      XX
      noface     XX      XX

--- Eye CNN ---
Evaluated on: xxx frames (face detected + crop valid)
Accuracy:  XX.X% (xxx/xxx)
Confusion Matrix:
              Pred
              OPEN  CLOSED
Actual eyeopen   XX      XX
      eyeclose   XX      XX

--- Eye CNN by Glass ---
With glass (xxx frames):    XX.X%
Without glass (xxx frames): XX.X%

--- Mouth CNN ---
Evaluated on: xxx frames (face detected + crop valid)
Accuracy:  XX.X% (xxx/xxx)
Confusion Matrix:
            Pred
            YAWN  NO_YAWN
Actual yawn     XX       XX
     noyawn     XX       XX

--- Seatbelt ---
Accuracy:  XX.X% (xxx/1002)
Confusion Matrix:
                Pred
                ON    OFF
Actual seatbelt    XX     XX
     noseatbelt    XX     XX

--- Mouth CNN (no-face frames) ---
Frames without face: xxx
All correctly predicted as NO_YAWN: xxx/xxx

======================================
Total runtime: XX.X seconds
======================================
```

## Rủi ro & câu hỏi mở

1. **Dataset imbalance**: eyeclose chỉ có 16/1002 ảnh (1.6%), yawn rất ít →
   accuracy có thể misleading (model luôn predict eyeopen đã đạt 98.4%).
   → **Giải pháp**: Báo cáo cả precision/recall/F1 per-class, không chỉ accuracy.

2. **FaceLandmarker cần MediaPipe model**: `face_landmarker.task` (~4MB) phải
   tồn tại trong `app/models/`. Không cần tải thêm.

3. **GPU memory**: Load 3 model large (YOLO face, YOLO seatbelt, MediaPipe)
   có thể tốn RAM/VRAM. Nếu chạy CPU, thời gian ~100-200ms/frame × 1002 =
   ~100-200 giây. Chấp nhận được cho offline eval.

4. **Mouth CNN khi no face**: Dữ liệu training của Mouth CNN không có ảnh
   "không có miệng". Khi no face, EyeCropper/MouthCropper không crop được
   → không gọi CNN. Thay vào đó, skip và tính riêng accuracy cho trường hợp
   này (expect NO_YAWN).

## Trạng thái xác nhận
`[x] Đã xác nhận bởi người dùng ngày 2026-07-16` — đã implement.
