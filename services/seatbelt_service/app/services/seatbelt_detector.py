"""YOLO-based seatbelt detector consuming frames from RabbitMQ.

Reuses ALL existing YOLO inference logic unchanged.
Replaces HTTP frame fetching with direct JPEG byte input.
"""

import os
import time
from typing import Optional

import numpy as np
from ultralytics import YOLO

from app.core.config import get_settings
from app.utils.logger import get_logger

CLASS_NAMES: dict[int, str] = {
    0: "cell phone",
    1: "drinking",
    2: "eyeglass",
    3: "hands off",
    4: "hands on",
    5: "mask",
    6: "seatbelt",
}
SEATBELT_CLASS_ID: int = 6


class SeatbeltDetector:
    """Encapsulates YOLO model loading and inference.

    Consumes JPEG frames received via RabbitMQ (passed as bytes),
    runs detection, and exposes results via thread-safe properties.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._model_path: str = settings.MODEL_PATH
        self._conf_threshold: float = settings.CONFIDENCE_THRESHOLD
        self._warning_frames: int = settings.WARNING_FRAMES

        self._model: Optional[YOLO] = None
        self._model_loaded: bool = False
        self._start_time: float = 0.0

        self._no_seatbelt_streak: int = 0
        self._total_checks: int = 0
        self._seatbelt_ok: int = 0
        self._seatbelt_missing: int = 0
        self._inference_times: list[float] = []

        self._logger = get_logger()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """Load the YOLO model from disk."""
        if self._model_loaded:
            return

        model_path = self._model_path
        if not os.path.isabs(model_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            model_path = os.path.join(base_dir, model_path)

        if not os.path.exists(model_path):
            self._logger.error("Model not found: %s", model_path)
            raise FileNotFoundError(f"YOLO model not found: {model_path}")

        self._logger.info("Loading YOLO model from %s", model_path)
        self._model = YOLO(model_path)
        self._model_loaded = True
        self._start_time = time.time()
        self._logger.info("Model loaded. Classes: %s", self._model.names)

    @property
    def is_loaded(self) -> bool:
        return self._model_loaded

    # ------------------------------------------------------------------
    # Detection (receives JPEG bytes directly instead of HTTP fetch)
    # ------------------------------------------------------------------

    def process(self, jpeg_bytes: bytes, frame_id: int, frame_timestamp: float) -> dict:
        """Process a JPEG frame received from RabbitMQ.

        Args:
            jpeg_bytes: Raw JPEG frame bytes.
            frame_id: Sequential frame identifier from camera.
            frame_timestamp: Unix timestamp from camera.

        Returns:
            dict with keys: frame_id, timestamp, seatbelt, confidence.
        """
        if not self._model_loaded or self._model is None:
            return self._build_result(frame_id, frame_timestamp, False, 0.0)

        t0 = time.time()

        frame_np = self._decode_jpeg(jpeg_bytes)
        if frame_np is None:
            return self._build_result(frame_id, frame_timestamp, False, 0.0)

        detections, has_seatbelt, max_confidence = self._run_inference(frame_np)
        inference_ms = (time.time() - t0) * 1000.0

        self._update_stats(has_seatbelt, inference_ms)

        return self._build_result(frame_id, frame_timestamp, has_seatbelt, max_confidence)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        uptime = time.time() - self._start_time if self._start_time > 0 else 0.0
        avg_inf = (
            sum(self._inference_times) / len(self._inference_times)
            if self._inference_times
            else 0.0
        )
        return {
            "uptime": round(uptime, 2),
            "total_checks": self._total_checks,
            "seatbelt_ok_count": self._seatbelt_ok,
            "seatbelt_missing_count": self._seatbelt_missing,
            "avg_inference_ms": round(avg_inf, 2),
        }

    # ------------------------------------------------------------------
    # Check endpoint (kept for backward compatibility with API)
    # ------------------------------------------------------------------

    def get_latest_result(self) -> dict:
        """Return the latest detection state for API /check endpoint."""
        return {
            "seatbelt_detected": self._no_seatbelt_streak == 0,
            "no_seatbelt_streak": self._no_seatbelt_streak,
            "warning": self._no_seatbelt_streak >= self._warning_frames,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_jpeg(jpeg_bytes: bytes) -> Optional[np.ndarray]:
        """Decode JPEG bytes to a numpy array (BGR)."""
        import cv2

        np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame

    def _run_inference(self, frame: np.ndarray) -> tuple[list[dict], bool, float]:
        """Run YOLO inference and return detections + seatbelt flag.

        KEPT EXACTLY AS IS from original implementation.
        """
        results = self._model(frame, conf=self._conf_threshold, verbose=False)
        boxes_data = results[0].boxes

        detections: list[dict] = []
        has_seatbelt = False
        max_seatbelt_confidence = 0.0

        if boxes_data is not None and len(boxes_data) > 0:
            for box in boxes_data:
                conf = float(box.conf[0])
                if conf < self._conf_threshold:
                    continue
                cls_id = int(box.cls[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                label = CLASS_NAMES.get(cls_id, str(cls_id))
                detections.append({
                    "class_name": label,
                    "class_id": cls_id,
                    "confidence": round(conf, 4),
                    "bbox": [x1, y1, x2, y2],
                })
                if cls_id == SEATBELT_CLASS_ID:
                    has_seatbelt = True
                    if conf > max_seatbelt_confidence:
                        max_seatbelt_confidence = conf

        return detections, has_seatbelt, max_seatbelt_confidence

    def _update_stats(self, has_seatbelt: bool, inference_ms: float) -> None:
        self._total_checks += 1
        if has_seatbelt:
            self._no_seatbelt_streak = 0
            self._seatbelt_ok += 1
        else:
            self._no_seatbelt_streak += 1
            self._seatbelt_missing += 1
        self._inference_times.append(inference_ms)
        if len(self._inference_times) > 1000:
            self._inference_times = self._inference_times[-1000:]

    @staticmethod
    def _build_result(frame_id: int, timestamp: float, seatbelt: bool, confidence: float) -> dict:
        return {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "seatbelt": seatbelt,
            "confidence": round(confidence, 4),
        }
