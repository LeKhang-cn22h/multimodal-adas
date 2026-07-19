"""Random Forest fatigue classifier.

TS-rf-integration:
    Loads a pre-trained Random Forest model from a pickle file,
    wraps it behind the IClassifier interface.
"""

from __future__ import annotations

import numpy as np

from app.schemas.classification_result import ClassificationResult
from app.services.classifier_interface import IClassifier
from app.services.feature_service import FeatureVector
from app.utils.logger import get_logger

logger = get_logger()


class RFClassifier(IClassifier):
    """scikit-learn Random Forest classifier adapter."""

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._model = None
        self._load_model()

    # ------------------------------------------------------------------
    # IClassifier implementation
    # ------------------------------------------------------------------

    @property
    def method(self) -> str:
        return "random_forest"

    def classify(self, features: FeatureVector) -> ClassificationResult:
        if self._model is None:
            return ClassificationResult(
                fatigue_score=-1,
                fatigue_level="Unknown",
                confidence=0.0,
                classification_method=self.method,
                features={},
            )

        arr = features.to_array().reshape(1, -1)
        pred = self._model.predict(arr)[0]

        # Try probability if available
        try:
            proba = self._model.predict_proba(arr)[0]
            confidence = float(np.max(proba))
        except (AttributeError, Exception):
            confidence = 0.7

        # Map numeric label → string
        label_map = {0: "Awake", 1: "Tired", 2: "Drowsy", 3: "Dangerous"}
        level = label_map.get(int(pred), "Unknown")

        return ClassificationResult(
            fatigue_score=int(pred),
            fatigue_level=level,
            confidence=confidence,
            classification_method=self.method,
            features=features.to_dict(),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        try:
            import joblib
            self._model = joblib.load(self._model_path)
            logger.info("RF model loaded from %s", self._model_path)
        except Exception as exc:
            logger.warning("Cannot load RF model: %s", exc)
            self._model = None
