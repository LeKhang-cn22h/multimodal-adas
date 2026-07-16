"""Drowsiness detection service.

Consumes JPEG frames, delegates face landmark detection to
FaceLandmarkerService, delegates feature extraction to FeatureService,
then classifies drowsiness via the injected IClassifier (DIP).

TS-fatigue-classifier: replaced the old EAR-threshold logic with a
pluggable classifier.  The detector no longer knows whether it is
using rule-based or ML classification.
"""

import time
from collections import Counter
from typing import Optional

import cv2
import numpy as np

from app.core.config import get_settings
from app.schemas.classification_result import FatigueLevel
from app.services.classifier_interface import IClassifier
from app.services.feature_service import FeatureService
from app.services.mediapipe_service import FaceLandmarkerService
from app.utils.logger import get_logger

logger = get_logger()

# Default (no-face) feature snapshot
_EMPTY_FEATURES: dict[str, float] = {
    "ear": 0.0, "perclos": 0.0, "mar": 0.0,
}


class FatigueDetector:
    """Encapsulates drowsiness detection pipeline.

    Receives frames (JPEG bytes), uses injected services for landmark
    extraction and feature engineering, then delegates classification
    to an IClassifier implementation.

    DIP: depends on IClassifier (abstract), not RuleBasedClassifier
    or RFClassifier directly.
    """

    def __init__(
        self,
        landmark_service: FaceLandmarkerService,
        feature_service: FeatureService,
        classifier: IClassifier,
    ) -> None:
        """Initialise with injected services (DIP).

        Args:
            landmark_service: Pre-loaded FaceLandmarkerService.
            feature_service:  FeatureService (wraps WindowedFeatureEngineer).
            classifier:       IClassifier implementation (rule-based or ML).
        """
        settings = get_settings()

        self._landmark_service: FaceLandmarkerService = landmark_service
        self._feature_service: FeatureService = feature_service
        self._classifier: IClassifier = classifier

        # ── Runtime statistics ──────────────────────────────────────
        self._total_frames: int = 0
        self._inference_times: list[float] = []
        self._start_time: float = 0.0

        # Fatigue level distribution (tracked per frame)
        self._level_counts: Counter[str] = Counter()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """Delegate to the underlying landmark service."""
        return self._landmark_service.is_loaded

    @property
    def classification_method(self) -> str:
        """Expose which classifier is currently active."""
        return self._classifier.method

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mark_ready(self) -> None:
        """Record the time when the detector becomes operational.

        Called by the orchestrator after the model is loaded and the
        messaging pipeline is started.
        """
        self._start_time = time.time()

    def process(
        self, jpeg_bytes: bytes, frame_id: int, frame_timestamp: float
    ) -> dict:
        """Process a single JPEG frame for drowsiness detection.

        Args:
            jpeg_bytes:      Raw JPEG frame bytes from RabbitMQ.
            frame_id:        Sequential frame identifier.
            frame_timestamp: Unix timestamp from the camera.

        Returns:
            dict matching the driver.result JSON schema.
        """
        t0 = time.time()

        frame = self._decode_jpeg(jpeg_bytes)
        if frame is None:
            return self._build_result(
                frame_id, frame_timestamp,
                fatigue_score=-1,
                fatigue_level="Unknown",
                confidence=0.0,
                classification_method=self._classifier.method,
                features=_EMPTY_FEATURES,
            )

        result = self._run_inference(frame, frame_id, frame_timestamp)
        inference_ms = (time.time() - t0) * 1000.0

        self._total_frames += 1
        self._inference_times.append(inference_ms)
        if len(self._inference_times) > 1000:
            self._inference_times = self._inference_times[-1000:]

        # Track fatigue level distribution
        self._level_counts[result["fatigue_level"]] += 1

        return result

    def get_stats(self) -> dict:
        """Return aggregated runtime statistics."""
        uptime = time.time() - self._start_time if self._start_time > 0 else 0.0
        avg_inf = (
            sum(self._inference_times) / len(self._inference_times)
            if self._inference_times
            else 0.0
        )
        return {
            "uptime": round(uptime, 2),
            "total_frames": self._total_frames,
            "avg_inference_ms": round(avg_inf, 2),
            "classification_method": self._classifier.method,
            "fatigue_level_distribution": dict(self._level_counts),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_jpeg(jpeg_bytes: bytes) -> Optional[np.ndarray]:
        """Decode JPEG bytes to BGR numpy array.

        Returns None when the bytes cannot be decoded as a valid JPEG.
        """
        np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame

    def _run_inference(
        self, frame: np.ndarray, frame_id: int, frame_timestamp: float
    ) -> dict:
        """Run landmark detection → feature extraction → classification.

        TS-fatigue-classifier: delegates to IClassifier.classify()
        instead of the old EAR-threshold logic.
        """
        timestamp_ms = int(time.time() * 1000)

        # 1. Landmark detection (via injected service)
        lm_result = self._landmark_service.detect(frame, timestamp_ms)

        # 2. Feature extraction (always called — pushes neutral roots
        #    if no face, to keep sliding windows alive)
        fv = self._feature_service.extract(lm_result, timestamp_ms)

        # 3. Classification
        if not lm_result.face_detected or lm_result.landmarks is None:
            return self._build_result(
                frame_id, frame_timestamp,
                fatigue_score=-1,
                fatigue_level="Unknown",
                confidence=0.0,
                classification_method=self._classifier.method,
                features=_EMPTY_FEATURES,
            )

        cr = self._classifier.classify(fv)

        return self._build_result(
            frame_id, frame_timestamp,
            fatigue_score=cr.fatigue_score,
            fatigue_level=cr.fatigue_level,
            confidence=cr.confidence,
            classification_method=cr.classification_method,
            features=cr.features,
        )

    @staticmethod
    def _build_result(
        frame_id: int,
        timestamp: float,
        fatigue_score: int,
        fatigue_level: FatigueLevel,
        confidence: float = 0.0,
        classification_method: str = "rule_based",
        features: Optional[dict[str, float]] = None,
    ) -> dict:
        """Build the result dictionary for RabbitMQ publishing.

        Schema khớp TS-fatigue-classifier § "Output Schema".
        """
        if features is None:
            features = _EMPTY_FEATURES

        return {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "fatigue_score": fatigue_score,
            "fatigue_level": fatigue_level,
            "confidence": round(confidence, 4),
            "classification_method": classification_method,
            "features": features,
        }
