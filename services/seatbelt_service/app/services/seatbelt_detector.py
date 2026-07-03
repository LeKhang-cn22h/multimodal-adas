"""YOLO-based seatbelt detector that fetches frames from camera-service."""

import os
import time
from typing import Optional

import httpx
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

    Fetches frames from camera-service via HTTP, runs detection,
    and exposes results via thread-safe properties.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._model_path: str = settings.MODEL_PATH
        self._conf_threshold: float = settings.CONFIDENCE_THRESHOLD
        self._warning_frames: int = settings.WARNING_FRAMES
        self._camera_url: str = settings.CAMERA_SERVICE_URL.rstrip("/") + "/frame"

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
    # Detection
    # ------------------------------------------------------------------

    def check_frame(self) -> dict:
        """Fetch one frame from camera-service and run YOLO detection.

        Returns a dictionary with detection results suitable for the API response.
        """
        if not self._model_loaded or self._model is None:
            raise RuntimeError("Model not loaded")

        t0 = time.time()

        frame_bytes = self._fetch_frame()
        if frame_bytes is None:
            return self._empty_result(time.time() - t0, "camera_unreachable")

        frame_np = self._decode_jpeg(frame_bytes)
        if frame_np is None:
            return self._empty_result(time.time() - t0, "decode_error")

        detections, has_seatbelt = self._run_inference(frame_np)
        inference_ms = (time.time() - t0) * 1000.0

        self._update_stats(has_seatbelt, inference_ms)

        return {
            "seatbelt_detected": has_seatbelt,
            "no_seatbelt_streak": self._no_seatbelt_streak,
            "warning": self._no_seatbelt_streak >= self._warning_frames,
            "detections": detections,
            "timestamp": time.time(),
            "inference_time_ms": round(inference_ms, 2),
        }

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
    # Internal
    # ------------------------------------------------------------------

    def _fetch_frame(self) -> Optional[bytes]:
        """Fetch JPEG frame from camera-service."""
        try:
            response = httpx.get(self._camera_url, timeout=5.0)
            if response.status_code == 200 and response.content:
                return response.content
            self._logger.warning("Camera returned status %d or empty body", response.status_code)
            return None
        except httpx.RequestError as exc:
            self._logger.warning("Camera unreachable: %s", exc)
            return None

    @staticmethod
    def _decode_jpeg(jpeg_bytes: bytes) -> Optional[np.ndarray]:
        """Decode JPEG bytes to a numpy array (BGR)."""
        import cv2

        np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame

    def _run_inference(self, frame: np.ndarray) -> tuple[list[dict], bool]:
        """Run YOLO inference and return detections + seatbelt flag."""
        results = self._model(frame, conf=self._conf_threshold, verbose=False)
        boxes_data = results[0].boxes

        detections: list[dict] = []
        has_seatbelt = False

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

        return detections, has_seatbelt

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

    def _empty_result(self, elapsed_ms: float, reason: str) -> dict:
        self._logger.debug("Empty result: %s (%.1fms)", reason, elapsed_ms)
        return {
            "seatbelt_detected": False,
            "no_seatbelt_streak": self._no_seatbelt_streak,
            "warning": False,
            "detections": [],
            "timestamp": time.time(),
            "inference_time_ms": round(elapsed_ms, 2),
        }
