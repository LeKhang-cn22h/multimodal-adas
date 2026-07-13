# TS-rf-integration: Tích hợp Random Forest vào Pipeline

## Thuộc Feature
`.opencode/knowledge/features/FEAT-rf-integration.md`

## Kiến trúc

### Tổng quan

Tích hợp model Random Forest (đã train từ FEAT-dataset-training) vào pipeline classification. Cơ chế: thử load model `.pkl` khi app khởi động; nếu thành công → dùng RF classifier; nếu thất bại → tự động fallback về `RuleBasedClassifier`. Pipeline chính (`FatigueDetector`) không cần biết đang dùng classifier nào — chỉ phụ thuộc vào `IClassifier` interface.

**Phạm vi**: driver-service ONLY.

### File sẽ tạo/sửa

| File | Hành động | Mô tả |
|---|---|---|
| `app/services/rf_classifier.py` | **TẠO MỚI** | `RFClassifier` implement `IClassifier`. Load model `.pkl`, gọi `predict_proba()` → map về Fatigue Score. |
| `app/services/classifier_interface.py` | **ĐÃ CÓ** (từ TS-fatigue-classifier) | Giữ nguyên. |
| `app/services/rule_based_classifier.py` | **ĐÃ CÓ** (từ TS-fatigue-classifier) | Giữ nguyên — dùng làm fallback. |
| `app/schemas/classification_result.py` | **ĐÃ CÓ** (từ TS-fatigue-classifier) | Giữ nguyên. |
| `app/messaging/orchestrator.py` | **SỬA** | Thêm logic: thử load RF model → nếu OK thì dùng `RFClassifier`, nếu fail → dùng `RuleBasedClassifier`. Inject vào `FatigueDetector`. |
| `app/core/config.py` | **SỬA** | Thêm `RF_MODEL_PATH`, `RF_FALLBACK_ENABLED`. |

### Luồng khởi động (lifespan)

```
MessagingOrchestrator.start()
    │
    ├── 1. FaceLandmarkerService.load_model()
    ├── 2. WindowedFeatureEngineer() → FeatureService()
    ├── 3. try:
    │       classifier = RFClassifier(model_path=RF_MODEL_PATH)
    │       log.info("RF model loaded successfully")
    │   except (FileNotFoundError, Exception) as e:
    │       log.warning(f"RF model not available: {e}")
    │       classifier = RuleBasedClassifier()
    │       log.info("Falling back to rule-based classifier")
    ├── 4. FatigueDetector(landmark_svc, feature_svc, classifier)
    └── 5. RabbitMQ connection → consumer → publisher
```

### Dependency graph

```
IClassifier (app/services/classifier_interface.py)
    ↑                           ↑
    │                           │
RuleBasedClassifier      RFClassifier (app/services/rf_classifier.py)
    (fallback)               ├── joblib / pickle
                             ├── numpy
                             └── app.core.config (RF_MODEL_PATH)

FatigueDetector
    └── IClassifier (inject)  ← DIP: không biết concrete class
```

## Logic + AI

### 1. RFClassifier

```python
import joblib
import logging
import numpy as np
from app.services.classifier_interface import IClassifier
from app.services.feature_service import FeatureVector
from app.schemas.classification_result import ClassificationResult, FatigueLevel

logger = logging.getLogger(__name__)

# Nhãn dùng khi train model. Phải khớp với TS-dataset-training.md
# § "Model Training" bảng Step 6:
#   y = numpy array (n_frames,), binary 0 (not drowsy) / 1 (drowsy)
# → model.classes_ = [0, 1], drowsy = label 1 = index 1.
_DROWSY_LABEL = 1

class RFClassifier(IClassifier):
    """Random Forest classifier for driver drowsiness detection.

    Loads a pre-trained model from a .pkl file (joblib format).
    Dynamically resolves the drowsy class index from model.classes_
    instead of hardcoding column index. Logs class mapping on load
    for manual verification.

    Model input:  (1, 40) float64 array (40-feature vector)
    Model output: binary classification (0 = not drowsy, 1 = drowsy)
    """

    def __init__(self, model_path: str) -> None:
        self._model = joblib.load(model_path)
        self._method = "random_forest"

        # ── Resolve drowsy class index dynamically ────────────────
        classes = list(self._model.classes_)
        logger.info(
            "RF model loaded. classes_=%s, num_classes=%d",
            classes, len(classes),
        )

        if _DROWSY_LABEL not in classes:
            raise ValueError(
                f"Drowsy label {_DROWSY_LABEL} not found in "
                f"model.classes_={classes}. Check training labels."
            )

        self._drowsy_idx = classes.index(_DROWSY_LABEL)
        logger.info(
            "Drowsy class resolved: label=%s → index=%d (verify manually "
            "against training/train_model.py label mapping)",
            _DROWSY_LABEL, self._drowsy_idx,
        )

    @property
    def method(self) -> str:
        return self._method

    def classify(self, features: FeatureVector) -> ClassificationResult:
        # 1. Convert FeatureVector → (1, 40) array
        X = features.to_array().reshape(1, -1)

        # 2. Get drowsiness probability (dynamic index, not hardcoded)
        proba = self._model.predict_proba(X)           # shape (1, n_classes)
        proba_drowsy = float(proba[0, self._drowsy_idx])

        # 3. Map probability → Fatigue Score (0-100)
        fatigue_score = min(100, max(0, int(proba_drowsy * 100)))

        # 4. Map score → Fatigue Level
        fatigue_level = self._score_to_level(fatigue_score)

        # 5. Confidence = model's probability for the predicted class
        confidence = round(
            proba_drowsy if fatigue_score >= 50 else (1.0 - proba_drowsy), 4
        )

        return ClassificationResult(
            fatigue_score=fatigue_score,
            fatigue_level=fatigue_level,
            confidence=confidence,
            classification_method=self._method,
            features={
                "ear": features.ear_avg,
                "perclos": features.perclos,
                "mar": features.mar,
                "yaw": features.yaw,
                "pitch": features.pitch,
                "roll": features.roll,
            }
        )

    @staticmethod
    def _score_to_level(score: int) -> FatigueLevel:
        if score <= 25:
            return "Awake"
        elif score <= 50:
            return "Tired"
        elif score <= 75:
            return "Drowsy"
        else:
            return "Dangerous"
```

#### Input / Output

| Thành phần | Kiểu | Mô tả |
|---|---|---|
| **Input** | `FeatureVector` (40 fields) | Từ `FeatureService.extract()` |
| **Input array** | `np.ndarray` shape `(1, 40)` dtype `float64` | Qua `fv.to_array().reshape(1, -1)` |
| **Model output** | `np.ndarray` shape `(1, 2)` | `predict_proba()` → `[p_not_drowsy, p_drowsy]` |
| **Fatigue Score** | `int` 0-100 | `int(p_drowsy * 100)` |
| **Fatigue Level** | `"Awake" \| "Tired" \| "Drowsy" \| "Dangerous"` | Mapping từ score |

#### Ngưỡng mapping Score → Level

| Score range | Level |
|---|---|
| 0–25 | Awake |
| 26–50 | Tired |
| 51–75 | Drowsy |
| 76–100 | Dangerous |

### 2. Cơ chế fallback (trong orchestrator.py)

```python
def _create_classifier(self) -> IClassifier:
    settings = get_settings()
    model_path = settings.RF_MODEL_PATH

    if not settings.RF_FALLBACK_ENABLED:
        # Fallback disabled → phải có model
        return RFClassifier(model_path)

    try:
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        classifier = RFClassifier(model_path)
        logger.info(f"Loaded RF model from {model_path}")
        return classifier
    except Exception as e:
        logger.warning(f"Cannot load RF model: {e}. Falling back to rule-based.")
        return RuleBasedClassifier()
```

### 3. Cấu hình mới trong `core/config.py`

```python
# ── Random Forest integration ──
RF_MODEL_PATH: str = os.getenv("RF_MODEL_PATH", "training/output/model.pkl")
RF_FALLBACK_ENABLED: bool = os.getenv("RF_FALLBACK_ENABLED", "true").lower() == "true"
```

### 4. Tích hợp với FatigueDetector

**Không thay đổi** `FatigueDetector` — nó đã nhận `IClassifier` qua constructor từ TS-fatigue-classifier. Đây là minh chứng cho DIP: thay đổi classifier implementation không cần sửa FatigueDetector.

### 5. Output Schema (không thay đổi từ TS-fatigue-classifier)

```json
{
  "frame_id": 1234,
  "timestamp": 1712345678.123,
  "fatigue_score": 72,
  "fatigue_level": "Drowsy",
  "confidence": 0.92,
  "classification_method": "random_forest",
  "features": { "ear": 0.15, "perclos": 35.2, "mar": 0.08,
                "yaw": -3.1, "pitch": 8.5, "roll": 1.2 }
}
```

Khác biệt duy nhất: `classification_method` = `"random_forest"` thay vì `"rule_based"`.

### Tích hợp với Layered Architecture

```
services/
    ├── classifier_interface.py      ← ĐÃ CÓ: IClassifier ABC
    ├── rule_based_classifier.py     ← ĐÃ CÓ: fallback
    ├── rf_classifier.py             ← TẠO MỚI: RFClassifier
    ├── feature_service.py           ← KHÔNG SỬA
    ├── mediapipe_service.py         ← KHÔNG SỬA
    └── fatigue_detector.py          ← KHÔNG SỬA (đã nhận IClassifier)

schemas/
    └── classification_result.py     ← KHÔNG SỬA

core/
    └── config.py                    ← SỬA: RF_MODEL_PATH, RF_FALLBACK_ENABLED

messaging/
    └── orchestrator.py              ← SỬA: load RF model, inject classifier
```

### Độ phức tạp & latency estimate

| Thành phần | Thời gian/frame | Ghi chú |
|---|---|---|
| `RFClassifier.classify()` | **~0.1ms** | `predict_proba()` trên 100 trees × depth 10, array (1, 40) |
| Load model (1 lần) | ~100ms | joblib deserialize, chỉ lúc startup |
| Model size | ≤ 10MB | 100 trees × depth 10 (khớp AC-5.3) |

## API Contract

**Không thêm API mới.** `GET /stats` cập nhật thêm `classification_method` hiện tại (`"random_forest"` hoặc `"rule_based"`).

## Rủi ro & câu hỏi mở

| Rủi ro | Mức độ | Giảm thiểu |
|---|---|---|
| **Model file không tồn tại** | Thấp | Tự động fallback về `RuleBasedClassifier`, log warning, không crash |
| **Model version mismatch** | Trung bình | Nếu 40-feature order thay đổi → model predict sai. Đảm bảo `FeatureVector.to_array()` order khớp training CSV. |
| **Model size > 10MB** | Thấp | RF 100 trees × depth 10 ≈ 5-8MB. Nếu vượt → giảm `n_estimators` hoặc `max_depth` khi train. |
| **Cold start: model chưa được train** | Thấp | Fallback về rule-based. App vẫn chạy bình thường. |

Không có câu hỏi mở.

## Ảnh hưởng tới service khác

- **driver-service**: Thay đổi internal — `classification_method` trong output JSON thay đổi từ `"rule_based"` sang `"random_forest"` khi model được load.
- **frontend / consumer khác**: Cần parse được cả 2 giá trị `classification_method`.

## Trạng thái xác nhận

`[X] Xác nhận`
