"""
Face Detector dùng YOLOv8-Face (ultralytics).

Nhiệm vụ DUY NHẤT: tìm bounding box của các khuôn mặt trong frame.
Không làm landmark — landmark vẫn do MediaPipe FaceLandmarker đảm nhiệm
(xem face_landmarker.py). Tách riêng detector giúp tận dụng khả năng tìm
mặt tốt hơn của YOLO (đặc biệt góc nghiêng, ánh sáng yếu) mà không phải
đụng vào toàn bộ pipeline landmark/EAR/MAR/head-pose đã ổn định.
"""

from __future__ import annotations

import numpy as np
from ultralytics import YOLO


class FaceDetector:

    def __init__(
        self,
        model_path: str = "app/models/yolov8n-face.pt",
        conf_threshold: float = 0.5,
        device: str = "cuda:0",
    ) -> None:
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.device = device

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Trả về list bbox (x1, y1, x2, y2) theo tọa độ PIXEL của frame gốc."""

        results = self.model.predict(
            frame,
            conf=self.conf_threshold,
            device=self.device,
            verbose=False,
        )

        bboxes: list[tuple[int, int, int, int]] = []

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                bboxes.append((int(x1), int(y1), int(x2), int(y2)))

        return bboxes