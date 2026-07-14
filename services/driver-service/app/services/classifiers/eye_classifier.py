"""
Eye classifier.

Input:
    Eye ROI (OpenCV BGR hoặc PIL)

Output:
    {
        "label": "OPEN",
        "confidence": 0.98
    }
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

from app.services.classifiers.image_preprocessor import ImagePreprocessor

from training.configs.eye_config import EyeConfig
from training.models.eye_cnn import build_eye_model


class EyeClassifier:

    def __init__(
        self,
        model_path: str | Path,
    ):

        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        cfg = EyeConfig()

        self.preprocess = ImagePreprocessor(
            cfg.img_size
        )

        self.model = build_eye_model(
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

        probability = torch.sigmoid(
            logits
        ).item()

        if probability >= 0.5:

            label = "OPEN"

            confidence = probability

        else:

            label = "CLOSED"

            confidence = 1.0 - probability

        return {
            "label": label,
            "confidence": float(confidence),
            "probability": float(probability),
        }