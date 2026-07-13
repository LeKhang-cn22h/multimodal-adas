"""RFClassifier — Random Forest classifier for driver drowsiness detection.

Implements IClassifier.  Loads a pre-trained model from a .pkl file
(joblib format), dynamically resolves the drowsy class index, and maps
predict_proba output to Fatigue Score + Fatigue Level.

Model input:  (1, 40) float64 array (40-feature vector)
Model output: binary classification (0 = not drowsy, 1 = drowsy)
"""

import logging

import joblib
import numpy as np

from app.schemas.classification_result import ClassificationResult, FatigueLevel
from app.services.classifier_interface import IClassifier
from app.services.feature_service import FeatureVector

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
    instead of hardcoding column index.  Logs class mapping on load
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

    # ------------------------------------------------------------------
    # IClassifier implementation
    # ------------------------------------------------------------------

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
            fatigue_level=fatigue_level,  # type: ignore[arg-type]
            confidence=confidence,
            classification_method=self._method,
            features={
                "ear": round(features.ear_avg, 4),
                "perclos": round(features.perclos, 4),
                "mar": round(features.mar, 4),
                "yaw": round(features.yaw, 4),
                "pitch": round(features.pitch, 4),
                "roll": round(features.roll, 4),
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
