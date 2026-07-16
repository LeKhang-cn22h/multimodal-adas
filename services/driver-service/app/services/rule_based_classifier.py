"""Rule-based fatigue classifier.

TS-fatigue-classifier:
    Implements IClassifier using hard-coded thresholds on PERCLOS
    and other features.  Used as fallback when the RF model cannot
    be loaded.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.schemas.classification_result import ClassificationResult
from app.services.classifier_interface import IClassifier
from app.services.feature_service import FeatureVector


class RuleBasedClassifier(IClassifier):
    """Simple threshold-based fatigue classifier."""

    def __init__(self) -> None:
        settings = get_settings()
        self._perclos_awake = settings.PERCLOS_AWAKE_MAX
        self._perclos_tired = settings.PERCLOS_TIRED_MAX
        self._perclos_drowsy = settings.PERCLOS_DROWSY_MAX

    @property
    def method(self) -> str:
        return "rule_based"

    def classify(self, features: FeatureVector) -> ClassificationResult:
        perclos = features.perclos

        if perclos <= self._perclos_awake:
            level = "Awake"
            score = int(perclos / self._perclos_awake * 50)
        elif perclos <= self._perclos_tired:
            level = "Tired"
            score = 50 + int(
                (perclos - self._perclos_awake)
                / (self._perclos_tired - self._perclos_awake) * 20
            )
        elif perclos <= self._perclos_drowsy:
            level = "Drowsy"
            score = 70 + int(
                (perclos - self._perclos_tired)
                / (self._perclos_drowsy - self._perclos_tired) * 20
            )
        else:
            level = "Dangerous"
            score = 90 + min(int((perclos - self._perclos_drowsy) / 20 * 10), 10)

        return ClassificationResult(
            fatigue_score=min(score, 100),
            fatigue_level=level,
            confidence=0.8,
            classification_method=self.method,
            features={
                "ear": features.ear_avg,
                "perclos": perclos,
                "mar": features.mar,
            },
        )
