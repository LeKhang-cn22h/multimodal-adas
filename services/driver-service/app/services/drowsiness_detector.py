"""
Drowsiness Detector — pipeline overlay real-time (TS-remove-headpose).

Pipeline

Frame
    │
    ▼
FaceLandmarker (multi-face via YOLO + MediaPipe)
    │
    ▼
DriverSelector (chọn khuôn mặt tài xế)
    │
    ▼
Crop Left Eye / Right Eye / Mouth
    │
    ├── crop_valid = True ──►  Eye CNN / Mouth CNN
    │       │
    │       ▼
    │   Geometric Verifier (EAR / MAR) — second opinion
    │       │
    │       ▼
    │   combine_eye_signal  /  combine_mouth_signal
    │       │
    │       ▼
    │   EyeStateBuffer  /  MouthStateBuffer
    │       │
    │       ▼
    │   Rule Engine  ──►  NORMAL | DROWSY
    │
    └── crop_valid = False ──►  FACE_DETECTED_BUT_INVALID

    │
    ▼
Overlay (Eye / Mouth / State)
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.drowsiness_config import DEFAULT_THRESHOLDS
from app.models.drowsiness_level import LEVEL_DISPLAY, DrowsinessLevel
from app.services.classifiers.predictor import Predictor
from app.services.decision.drowsiness_rule_engine import DrowsinessRuleEngine
from app.services.driver_selector import DriverSelector
from app.services.eye_cropper import EyeCropper
from app.services.face_detector import FaceDetector
from app.services.face_landmarker import FaceLandmarker
from app.services.geometric_verifier import (
    GeometricVerifier,
    combine_eye_signal,
    combine_mouth_signal,
)
from app.services.mouth_cropper import MouthCropper
from app.services.temporal.eye_state_buffer import EyeStateBuffer
from app.services.temporal.mouth_state_buffer import MouthStateBuffer


class DrowsinessDetector:

    def __init__(
        self,
        eye_model_path: str,
        mouth_model_path: str,
    ) -> None:

        self.eye_cropper = EyeCropper()
        self.mouth_cropper = MouthCropper()

        self.predictor = Predictor(
            eye_model_path=eye_model_path,
            mouth_model_path=mouth_model_path,
        )

        thresholds = DEFAULT_THRESHOLDS

        self.driver_selector = DriverSelector(thresholds)
        self.eye_buffer = EyeStateBuffer(thresholds)
        self.mouth_buffer = MouthStateBuffer(thresholds)
        self.rule_engine = DrowsinessRuleEngine()
        self.geometric_verifier = GeometricVerifier()
        self.landmarker = FaceLandmarker(face_detector=FaceDetector())

    def _get_all_landmarks(
        self,
        frame: np.ndarray,
        timestamp: float | None = None,
    ) -> list[list[tuple[int, int]]]:

        timestamp_ms = int(timestamp * 1000) if timestamp is not None else None

        if hasattr(self.landmarker, "detect_all"):
            return self.landmarker.detect_all(frame, timestamp_ms)

        single = self.landmarker.detect(frame, timestamp_ms)
        return [single] if single is not None else []

    def _draw_overlay(
        self,
        frame: np.ndarray,
        level: DrowsinessLevel,
        eye_result: dict | None,
        mouth_result: dict | None,
    ) -> np.ndarray:

        display = LEVEL_DISPLAY[level]
        color = display["color"]

        y = 50

        if eye_result is not None:
            cv2.putText(
                frame,
                f"Eye : {eye_result['label']} ({eye_result['confidence']:.2f})",
                (20, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3,
            )
            y += 45

        if mouth_result is not None:
            cv2.putText(
                frame,
                f"Mouth : {mouth_result['label']} ({mouth_result['confidence']:.2f})",
                (20, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3,
            )
            y += 45

        cv2.putText(
            frame,
            f"State : {display['text']}",
            (20, y), cv2.FONT_HERSHEY_SIMPLEX, 1.3, color, 3,
        )

        if level in (DrowsinessLevel.DROWSY, DrowsinessLevel.NO_FACE):
            cv2.rectangle(
                frame, (0, 0), (frame.shape[1], frame.shape[0]), color, 6,
            )
            cv2.putText(
                frame, f"WARNING : {display['text']}",
                (20, y + 55), cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 4,
            )

        return frame

    def process(self, frame: np.ndarray, timestamp: float | None = None):
        all_landmarks = self._get_all_landmarks(frame, timestamp)
        landmarks = self.driver_selector.select(frame.shape, all_landmarks)

        face_detected = landmarks is not None

        eye_result = None
        mouth_result = None
        eye_buffer_result = None
        mouth_buffer_result = None
        crop_valid = False

        if landmarks is not None:
            left_eye_roi = self.eye_cropper.crop_left(frame, landmarks)
            right_eye_roi = self.eye_cropper.crop_right(frame, landmarks)
            mouth_roi = self.mouth_cropper.crop(frame, landmarks)

            if left_eye_roi is not None and right_eye_roi is not None and mouth_roi is not None:
                crop_valid = True

                result = self.predictor.predict(left_eye_roi, right_eye_roi, mouth_roi)
                eye_result = result["eye"]
                mouth_result = result["mouth"]

                eye_geo = self.geometric_verifier.verify_eye(landmarks)
                mouth_geo = self.geometric_verifier.verify_mouth(landmarks)

                eye_result["label"] = combine_eye_signal(eye_result["label"], eye_geo)
                mouth_result["label"] = combine_mouth_signal(mouth_result["label"], mouth_geo)

                eye_result["ear"] = eye_geo["avg_ear"]
                mouth_result["mar"] = mouth_geo["mar"]

                eye_buffer_result = self.eye_buffer.update(
                    is_closed=(eye_result["label"] == "CLOSED"),
                    now=timestamp,
                )
                mouth_buffer_result = self.mouth_buffer.update(
                    is_yawn=(mouth_result["label"] == "YAWN"),
                    now=timestamp,
                )

        level = self.rule_engine.decide(
            face_detected=face_detected,
            crop_valid=crop_valid,
            eye_buffer_result=eye_buffer_result,
            mouth_buffer_result=mouth_buffer_result,
        )

        frame = self._draw_overlay(frame, level, eye_result, mouth_result)

        result_payload = {
            "level": level,
            "eye": eye_result,
            "mouth": mouth_result,
            "eye_buffer": eye_buffer_result,
            "mouth_buffer": mouth_buffer_result,
        }

        return frame, result_payload
