"""Face Landmarker service wrapping MediaPipe Face Landmarker.

Extracted from FatigueDetector per FEAT-landmark-refactor / TS-landmark-refactor.
Provides a clean interface for face landmark detection without coupling to
business logic (EAR, drowsiness, etc.).

ADR-004: Uses Face Landmarker (478 landmarks, face_landmarker.task).
Head Pose input (facial_transformation_matrixes) is passed through
FaceLandmarkerResult for downstream feature extraction.
"""

import time
from dataclasses import dataclass
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

from app.utils.logger import get_logger

# ---------------------------------------------------------------------------
# MediaPipe task API imports
# ---------------------------------------------------------------------------
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

logger = get_logger()


# =============================================================================
#  FaceLandmarkerResult — internal DTO (not serialised via JSON)
# =============================================================================


@dataclass
class FaceLandmarkerResult:
    """Structured result from FaceLandmarkerService.detect().

    All fields are extracted directly from MediaPipe Face Landmarker output,
    with no intermediate transformation.

    This is NOT a Pydantic model because it contains numpy arrays that
    cannot be serialised to JSON natively.  It is an internal DTO used
    only within the service / messaging layers.
    """

    # ── Field 1: face detection flag ──────────────────────────────────
    face_detected: bool
    # True when at least one face was found in the frame.
    # When False, both landmarks and transformation_matrix are None.

    # ── Field 2: 478 facial landmarks ─────────────────────────────────
    landmarks: Optional[list]
    # list[mp.tasks.vision.NormalizedLandmark] — length 478.
    # Each element exposes .x, .y, .z (normalised coordinates [0, 1]).
    # Source: result.face_landmarks[0]  (num_faces=1 — first face only).

    # ── Field 3: transformation matrix for Head Pose ──────────────────
    transformation_matrix: Optional[np.ndarray]
    # 4×4 float64 matrix, shape (4, 4).
    # Source: result.facial_transformation_matrixes[0].
    # Used by utils/headpose.py (FEAT-feature-extraction) per ADR-004.
    # None when face_detected=False OR MediaPipe does not return a matrix.


# =============================================================================
#  FaceLandmarkerService
# =============================================================================


class FaceLandmarkerService:
    """Wraps MediaPipe Face Landmarker for face detection & landmark extraction.

    Responsibilities:
    - Load the model ONCE (call load_model() during app startup).
    - Accept BGR numpy frames, run inference, return FaceLandmarkerResult.
    - Release the model on shutdown via close_model().

    This class does NOT know about EAR, drowsiness, or any business logic.
    """

    def __init__(self, model_path: str) -> None:
        """Store model path; the model is NOT loaded yet.

        Args:
            model_path: Path to face_landmarker.task.
        """
        self._model_path: str = model_path
        self._landmarker: Optional[FaceLandmarker] = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """Return True if the MediaPipe model has been loaded."""
        return self._landmarker is not None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """Create the FaceLandmarker instance from the model file.

        Idempotent — does nothing if already loaded.
        """
        if self._landmarker is not None:
            return

        logger.info("Loading MediaPipe Face Landmarker from %s", self._model_path)
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=self._model_path),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=1,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)
        logger.info("MediaPipe Face Landmarker loaded")

    def close_model(self) -> None:
        """Release the underlying MediaPipe model."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
            logger.info("MediaPipe Face Landmarker released")

    # ------------------------------------------------------------------
    # Core inference
    # ------------------------------------------------------------------

    def detect(
        self,
        frame: np.ndarray,
        timestamp_ms: int,
    ) -> FaceLandmarkerResult:
        """Run face landmark detection on a BGR frame.

        Args:
            frame:        BGR image as numpy array, shape (H, W, 3), dtype uint8.
            timestamp_ms: Monotonic timestamp in milliseconds (required by
                          FaceLandmarker VIDEO mode).

        Returns:
            FaceLandmarkerResult with detection flag, landmarks list,
            and transformation matrix.  All fields are None when no face
            is detected.

        Raises:
            RuntimeError: If the model has not been loaded yet.
        """
        if self._landmarker is None:
            raise RuntimeError(
                "FaceLandmarkerService.detect() called before load_model()"
            )

        # MediaPipe VIDEO mode requires an mp.Image in SRGB format.
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        # ── No face detected ──────────────────────────────────────────
        if not result.face_landmarks:
            return FaceLandmarkerResult(
                face_detected=False,
                landmarks=None,
                transformation_matrix=None,
            )

        # ── Face detected — extract from MediaPipe result ────────────
        landmarks = result.face_landmarks[0]  # first (and only) face

        # Extract transformation matrix for Head Pose (ADR-004).
        # MediaPipe guarantees this field when face_landmarks is non-empty.
        matrix: Optional[np.ndarray] = None
        if result.facial_transformation_matrixes:
            matrix = np.array(
                result.facial_transformation_matrixes[0], dtype=np.float64
            )

        return FaceLandmarkerResult(
            face_detected=True,
            landmarks=landmarks,
            transformation_matrix=matrix,
        )
