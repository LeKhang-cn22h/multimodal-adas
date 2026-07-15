"""
Predictor.

Load cả Eye CNN và Mouth CNN một lần.

Đây là interface duy nhất mà drowsiness detector sử dụng.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.services.classifiers.eye_classifier import EyeClassifier
from app.services.classifiers.mouth_classifier import MouthClassifier


class Predictor:

    def __init__(
        self,
        eye_model_path: str | Path,
        mouth_model_path: str | Path,
    ) -> None:

        self.eye_classifier = EyeClassifier(
            eye_model_path,
        )

        self.mouth_classifier = MouthClassifier(
            mouth_model_path,
        )

    def predict_eye(
        self,
        eye_roi: np.ndarray | Image.Image,
    ) -> dict:

        return self.eye_classifier.predict(
            eye_roi,
        )

    def predict_mouth(
        self,
        mouth_roi: np.ndarray | Image.Image,
    ) -> dict:

        return self.mouth_classifier.predict(
            mouth_roi,
        )

    def predict(
        self,
        eye_roi: np.ndarray | Image.Image,
        mouth_roi: np.ndarray | Image.Image,
    ) -> dict:

        eye_result = self.predict_eye(
            eye_roi,
        )

        mouth_result = self.predict_mouth(
            mouth_roi,
        )

        return {
            "eye": eye_result,
            "mouth": mouth_result,
        }