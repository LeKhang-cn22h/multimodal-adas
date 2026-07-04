"""Drowsiness detection service wrapping MediaPipe Face Landmarker.

Reuses ALL existing AI logic from the standalone driver main.py:
- MediaPipe Face Landmarker (face_landmarker.task)
- EAR calculation per eye
- Sliding window for closed eye frames
- Drowsy threshold

ONLY changes: input source (JPEG bytes from RabbitMQ instead of webcam).
"""

import time
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

from app.core.config import get_settings
from app.utils.ear import LEFT_EYE, RIGHT_EYE, calculate_ear
from app.utils.logger import get_logger

BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

logger = get_logger()


class FatigueDetector:
    """Encapsulates MediaPipe-based drowsiness detection.

    Consumes JPEG frames, runs face landmark detection and EAR
    calculation, and produces drowsiness results.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._ear_threshold: float = settings.EAR_THRESHOLD
        self._drowsy_frames: int = settings.DROWSY_FRAMES
        self._model_path: str = settings.MODEL_PATH
        self._sliding_window_size: int = settings.SLIDING_WINDOW_SIZE

        self._landmarker: Optional[FaceLandmarker] = None
        self._closed_eye_frames: int = 0
        self._ear_history: list[float] = []

        self._total_frames: int = 0
        self._drowsy_event_count: int = 0
        self._inference_times: list[float] = []
        self._start_time: float = 0.0

    @property
    def is_loaded(self) -> bool:
        return self._landmarker is not None

    def load_model(self) -> None:
        """Load the MediaPipe Face Landmarker model."""
        if self._landmarker is not None:
            return

        logger.info("Loading MediaPipe model from %s", self._model_path)
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=self._model_path),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=1,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)
        self._start_time = time.time()
        logger.info("MediaPipe model loaded")

    def close_model(self) -> None:
        """Release the MediaPipe model."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
            logger.info("MediaPipe model released")

    def process(self, jpeg_bytes: bytes, frame_id: int, frame_timestamp: float) -> dict:
        """Process a single JPEG frame for drowsiness detection.

        Args:
            jpeg_bytes: Raw JPEG frame bytes.
            frame_id: Sequential frame identifier.
            frame_timestamp: Unix timestamp from camera.

        Returns:
            dict with keys: frame_id, timestamp, sleepy, confidence.
        """
        t0 = time.time()

        frame = self._decode_jpeg(jpeg_bytes)
        if frame is None:
            return self._build_result(frame_id, frame_timestamp, False, 0.0, t0)

        result = self._run_inference(frame, frame_id, frame_timestamp)
        inference_ms = (time.time() - t0) * 1000.0

        self._total_frames += 1
        self._inference_times.append(inference_ms)
        if len(self._inference_times) > 1000:
            self._inference_times = self._inference_times[-1000:]

        if result["sleepy"]:
            self._drowsy_event_count += 1

        return result

    def get_stats(self) -> dict:
        uptime = time.time() - self._start_time if self._start_time > 0 else 0.0
        avg_inf = (
            sum(self._inference_times) / len(self._inference_times)
            if self._inference_times
            else 0.0
        )
        return {
            "uptime": round(uptime, 2),
            "total_frames": self._total_frames,
            "drowsy_events": self._drowsy_event_count,
            "closed_eye_frames": self._closed_eye_frames,
            "avg_inference_ms": round(avg_inf, 2),
            "avg_ear": round(sum(self._ear_history) / len(self._ear_history), 4) if self._ear_history else 0.0,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_jpeg(jpeg_bytes: bytes) -> Optional[np.ndarray]:
        """Decode JPEG bytes to BGR numpy array."""
        np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame

    def _run_inference(self, frame: np.ndarray, frame_id: int, frame_timestamp: float) -> dict:
        """Run MediaPipe inference and EAR-based drowsiness detection.

        Uses the SLIDING WINDOW approach: tracks closed_eye_frames counter.
        If EAR < threshold for DROWSY_FRAMES consecutive frames → sleepy = True.
        """
        if self._landmarker is None:
            return self._build_result(frame_id, frame_timestamp, False, 0.0, time.time())

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = int(time.time() * 1000)

        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.face_landmarks:
            return self._build_result(frame_id, frame_timestamp, False, 0.0, time.time())

        landmarks = result.face_landmarks[0]

        left_ear = calculate_ear(landmarks, LEFT_EYE)
        right_ear = calculate_ear(landmarks, RIGHT_EYE)
        ear = (left_ear + right_ear) / 2.0

        self._ear_history.append(ear)
        if len(self._ear_history) > self._sliding_window_size:
            self._ear_history.pop(0)

        if ear < self._ear_threshold:
            self._closed_eye_frames += 1
        else:
            self._closed_eye_frames = 0

        sleepy = self._closed_eye_frames > self._drowsy_frames

        confidence = 1.0 - (ear / self._ear_threshold) if ear < self._ear_threshold else ear / 0.35
        confidence = max(0.0, min(1.0, float(confidence)))

        return self._build_result(frame_id, frame_timestamp, sleepy, confidence, time.time())

    @staticmethod
    def _build_result(
        frame_id: int, timestamp: float, sleepy: bool, confidence: float, _inference_time: float
    ) -> dict:
        return {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "sleepy": sleepy,
            "confidence": round(confidence, 4),
        }
