"""
Mouth classifier.

Input:
    Mouth ROI (OpenCV BGR hoặc PIL)

Output:
    {
        "label": "YAWN",
        "confidence": 0.95
    }
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.services.classifiers.image_preprocessor import ImagePreprocessor

from training.configs.mouth_config import MouthConfig
from training.models.mouth_cnn import build_mouth_model


class MouthClassifier:

    def __init__(
        self,
        model_path: str | Path,
    ) -> None:

        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        cfg = MouthConfig()

        self.preprocess = ImagePreprocessor(
            cfg.img_size
        )

        self.model = build_mouth_model(
            self.device
        )

        state = torch.load(
            model_path,
            map_location=self.device,
        )

        if isinstance(state, dict) and "model_state_dict" in state:
            state = state["model_state_dict"]

        self.model.load_state_dict(state)

        self.model.eval()

    @torch.no_grad()
    def predict(
        self,
        image: np.ndarray | Image.Image,
    ) -> dict:

        tensor = self.preprocess(image)
        tensor = tensor.to(self.device)

        logits = self.model(tensor)
        probability = torch.sigmoid(logits).item()

        # probability = P(Yawn)  (class 1 theo ImageFolder alphabet: no_yawn=0, yawn=1)

        if probability >= 0.5:
            label = "YAWN"
            confidence = probability
        else:
            label = "NO_YAWN"
            confidence = 1.0 - probability

        return {
            "label": label,
            "confidence": float(confidence),
            "probability": float(probability),
        }