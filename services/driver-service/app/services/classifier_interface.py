"""IClassifier — abstract interface for fatigue classification.

All classifiers (RuleBasedClassifier, RFClassifier, ...) implement
this single contract so that FatigueDetector never depends on a
concrete class (Dependency Inversion Principle).
"""

from abc import ABC, abstractmethod

from app.schemas.classification_result import ClassificationResult
from app.services.feature_service import FeatureVector


class IClassifier(ABC):
    """Abstract classifier that maps a 40-feature vector to a fatigue result."""

    @abstractmethod
    def classify(self, features: FeatureVector) -> ClassificationResult:
        """Classify fatigue from a 40-feature vector.

        Args:
            features: 40-field vector from FeatureService.extract().

        Returns:
            ClassificationResult with score, level, confidence, and method.
        """
        ...

    @property
    @abstractmethod
    def method(self) -> str:
        """Human-readable classifier name (e.g. "rule_based", "random_forest")."""
        ...
