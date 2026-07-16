from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.services.classifiers.eye_classifier import EyeClassifier
from app.services.classifiers.mouth_classifier import MouthClassifier


class Predictor:

    def __init__(self, eye_model_path: str | Path, mouth_model_path: str | Path) -> None:
        self.eye_classifier = EyeClassifier(eye_model_path)
        self.mouth_classifier = MouthClassifier(mouth_model_path)

    def predict_eyes(self, left_eye_roi, right_eye_roi) -> dict:

        left = self.eye_classifier.predict(left_eye_roi)
        right = self.eye_classifier.predict(right_eye_roi)

        avg_prob = (left["probability"] + right["probability"]) / 2

        if avg_prob >= 0.5:
            label = "OPEN"
            confidence = avg_prob
        else:
            label = "CLOSED"
            confidence = 1.0 - avg_prob

        return {
            "label": label,
            "confidence": float(confidence),
            "probability": float(avg_prob),
            "left": left,
            "right": right,
        }

    def predict_mouth(self, mouth_roi) -> dict:
        return self.mouth_classifier.predict(mouth_roi)

    def predict(self, left_eye_roi, right_eye_roi, mouth_roi) -> dict:

        eye_result = self.predict_eyes(left_eye_roi, right_eye_roi)
        mouth_result = self.predict_mouth(mouth_roi)

        return {
            "eye": eye_result,
            "mouth": mouth_result,
        }