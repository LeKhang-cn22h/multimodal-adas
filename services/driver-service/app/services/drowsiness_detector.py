"""
Drowsiness Detector.

Pipeline

Frame
    │
    ▼
FaceMesh
    │
    ▼
Crop Eye
    │
    ▼
Eye CNN
    │
    ▼
Crop Mouth
    │
    ▼
Mouth CNN
    │
    ▼
Decision
    │
    ▼
Overlay
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services.classifiers.predictor import Predictor
from app.services.eye_cropper import EyeCropper
from app.services.face_landmarker import FaceLandmarker
from app.services.mouth_cropper import MouthCropper


class DrowsinessDetector:

    def __init__(
        self,
        eye_model_path: str,
        mouth_model_path: str,
    ) -> None:

        self.landmarker = FaceLandmarker()

        self.eye_cropper = EyeCropper()

        self.mouth_cropper = MouthCropper()

        self.predictor = Predictor(
            eye_model_path=eye_model_path,
            mouth_model_path=mouth_model_path,
        )

    def _decision(
        self,
        eye_label: str,
        mouth_label: str,
    ) -> str:

        if eye_label == "OPEN" and mouth_label == "NO_YAWN":
            return "AWAKE"

        if eye_label == "CLOSED" and mouth_label == "NO_YAWN":
            return "EYES CLOSED"

        if eye_label == "OPEN" and mouth_label == "YAWN":
            return "YAWNING"

        return "DROWSY"

    def process(
        self,
        frame: np.ndarray,
    ):

        landmarks = self.landmarker.detect(frame)

        if landmarks is None:

            cv2.putText(
                frame,
                "NO FACE",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
            )

            return frame, None

        left_eye_roi = self.eye_cropper.crop_left(frame, landmarks)
        right_eye_roi = self.eye_cropper.crop_right(frame, landmarks)
        mouth_roi = self.mouth_cropper.crop(frame, landmarks)
        if mouth_roi is not None:
            cv2.imshow("Mouth ROI DEBUG", cv2.resize(mouth_roi, (200, 200)))

        if left_eye_roi is None or right_eye_roi is None or mouth_roi is None:
            return frame, None

        result = self.predictor.predict(
            left_eye_roi,
            right_eye_roi,
            mouth_roi,
        )

        state = self._decision(
            result["eye"]["label"],
            result["mouth"]["label"],
        )

        color = (0, 255, 0)

        if state == "DROWSY":
            color = (0, 0, 255)

        elif state == "YAWNING":
            color = (0, 255, 255)

        elif state == "EYES CLOSED":
            color = (255, 255, 0)

        cv2.putText(
            frame,
            f"Eye : {result['eye']['label']} ({result['eye']['confidence']:.2f})",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )

        cv2.putText(
            frame,
            f"Mouth : {result['mouth']['label']} ({result['mouth']['confidence']:.2f})",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )

        cv2.putText(
            frame,
            f"State : {state}",
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            color,
            2,
        )

        if state == "DROWSY":

            cv2.rectangle(
                frame,
                (0, 0),
                (frame.shape[1], frame.shape[0]),
                (0, 0, 255),
                6,
            )

            cv2.putText(
                frame,
                "WARNING : DROWSINESS DETECTED",
                (20, 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                3,
            )

        return frame, result