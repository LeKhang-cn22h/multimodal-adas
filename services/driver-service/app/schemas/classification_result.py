"""ClassificationResult — data contract between classifier and FatigueDetector.

This dataclass carries the output of any IClassifier implementation
(rule-based or ML).  No business logic here — pure DTO.
"""

from dataclasses import dataclass, field
from typing import Literal

FatigueLevel = Literal["Awake", "Tired", "Drowsy", "Dangerous", "Unknown"]


@dataclass
class ClassificationResult:
    """Output of a single fatigue classification.

    Attributes:
        fatigue_score:         0-100 (continuous), -1 if face not detected.
        fatigue_level:         Human-readable label.
        confidence:            0.0-1.0, how confident the classifier is.
        classification_method: "rule_based" | "random_forest".
        features:              Snapshot of key features for debugging/logging.
    """

    fatigue_score: int                  # 0-100, -1 = Unknown
    fatigue_level: FatigueLevel
    confidence: float                   # 0.0 - 1.0
    classification_method: str          # "rule_based" | "random_forest"
    features: dict[str, float] = field(default_factory=dict)
