"""FeatureService — orchestrates per-frame feature extraction.

Receives FaceLandmarkerResult, delegates root-feature computation to
utils/*.py, delegates windowed features to WindowedFeatureEngineer,
and returns a 40-field FeatureVector.

FeatureVector field order EXACTLY matches dataset_features.csv columns
so that model.predict(array) receives the correct input.
"""

from dataclasses import dataclass, asdict

import numpy as np

from app.services.mediapipe_service import FaceLandmarkerResult
from app.services.feature_engineering import WindowedFeatureEngineer
from app.utils.ear import LEFT_EYE, RIGHT_EYE, calculate_ear
from app.utils.mar import calculate_mar
from app.utils.headpose import extract_head_pose


# =============================================================================
#  FeatureVector — 40-field internal DTO
# =============================================================================


@dataclass
class FeatureVector:
    """40-feature vector matching the training CSV schema.

    When face is NOT detected all fields default to 0.0.

    Field order is CRITICAL — must match the column order in
    dataset_features.csv used by model training (RF / XGBoost).
    See TS-dataset-training.md § "Danh sách feature cuối cùng".
    """

    # ── A. Root features (7) — per-frame ──────────────────────────────
    ear_left: float = 0.0       #  1
    ear_right: float = 0.0      #  2
    ear_avg: float = 0.0        #  3
    mar: float = 0.0            #  4
    yaw: float = 0.0            #  5
    pitch: float = 0.0          #  6
    roll: float = 0.0           #  7

    # ── B. Sliding-window statistics (28) — N=300 backward ────────────
    ear_left_mean: float = 0.0  #  8
    ear_left_std: float = 0.0   #  9
    ear_left_min: float = 0.0   # 10
    ear_left_max: float = 0.0   # 11
    ear_right_mean: float = 0.0 # 12
    ear_right_std: float = 0.0  # 13
    ear_right_min: float = 0.0  # 14
    ear_right_max: float = 0.0  # 15
    ear_avg_mean: float = 0.0   # 16
    ear_avg_std: float = 0.0    # 17
    ear_avg_min: float = 0.0    # 18
    ear_avg_max: float = 0.0    # 19
    mar_mean: float = 0.0       # 20
    mar_std: float = 0.0        # 21
    mar_min: float = 0.0        # 22
    mar_max: float = 0.0        # 23
    yaw_mean: float = 0.0       # 24
    yaw_std: float = 0.0        # 25
    yaw_min: float = 0.0        # 26
    yaw_max: float = 0.0        # 27
    pitch_mean: float = 0.0     # 28
    pitch_std: float = 0.0      # 29
    pitch_min: float = 0.0      # 30
    pitch_max: float = 0.0      # 31
    roll_mean: float = 0.0      # 32
    roll_std: float = 0.0       # 33
    roll_min: float = 0.0       # 34
    roll_max: float = 0.0       # 35

    # ── C. Temporal / behavioral (5) — backward window ────────────────
    perclos: float = 0.0        # 36  N=900 (30 s)
    blink_rate: float = 0.0     # 37  N=900 (30 s)
    yaw_velocity: float = 0.0   # 38  N=30  (1 s)
    pitch_velocity: float = 0.0 # 39  N=30  (1 s)
    roll_velocity: float = 0.0  # 40  N=30  (1 s)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_array(self) -> np.ndarray:
        """Return (40,) float64 array suitable for model.predict()."""
        return np.array([
            self.ear_left, self.ear_right, self.ear_avg,
            self.mar, self.yaw, self.pitch, self.roll,
            self.ear_left_mean, self.ear_left_std, self.ear_left_min, self.ear_left_max,
            self.ear_right_mean, self.ear_right_std, self.ear_right_min, self.ear_right_max,
            self.ear_avg_mean, self.ear_avg_std, self.ear_avg_min, self.ear_avg_max,
            self.mar_mean, self.mar_std, self.mar_min, self.mar_max,
            self.yaw_mean, self.yaw_std, self.yaw_min, self.yaw_max,
            self.pitch_mean, self.pitch_std, self.pitch_min, self.pitch_max,
            self.roll_mean, self.roll_std, self.roll_min, self.roll_max,
            self.perclos, self.blink_rate,
            self.yaw_velocity, self.pitch_velocity, self.roll_velocity,
        ], dtype=np.float64)

    def to_dict(self) -> dict[str, float]:
        """Return all 40 fields as a plain dict."""
        return asdict(self)


# =============================================================================
#  FeatureService — orchestrator
# =============================================================================


class FeatureService:
    """Orchestrate feature extraction from a FaceLandmarkerResult.

    Responsibilities:
    1. Compute 7 root features (EAR, MAR, HeadPose) via utils/*.py.
    2. Delegate to WindowedFeatureEngineer for all 40 features.
    3. Return a FeatureVector.

    DIP: WindowedFeatureEngineer is injected via constructor.
    """

    def __init__(self, engine: WindowedFeatureEngineer) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        result: FaceLandmarkerResult,
        timestamp_ms: int,
    ) -> FeatureVector:
        """Extract all 40 features from one frame's landmarker result.

        Args:
            result:       Output from FaceLandmarkerService.detect().
            timestamp_ms: Monotonic timestamp (matching MediaPipe VIDEO mode).
                          Currently unused but reserved for future
                          timestamp-based window variants.

        Returns:
            FeatureVector with 40 fields.  All zeros when no face is detected.
        """
        _ = timestamp_ms  # reserved

        if not result.face_detected or result.landmarks is None:
            # ── No face → push neutral values so window stays alive ─────
            self._engine.update(_NEUTRAL_ROOTS)
            return FeatureVector()  # all zeros

        # ── Compute 7 root features ────────────────────────────────────
        landmarks = result.landmarks

        ear_left = calculate_ear(landmarks, LEFT_EYE)
        ear_right = calculate_ear(landmarks, RIGHT_EYE)
        ear_avg = (ear_left + ear_right) / 2.0

        mar = calculate_mar(landmarks)

        yaw, pitch, roll = (0.0, 0.0, 0.0)
        if result.transformation_matrix is not None:
            yaw, pitch, roll = extract_head_pose(result.transformation_matrix)

        roots: dict[str, float] = {
            "ear_left": float(ear_left),
            "ear_right": float(ear_right),
            "ear_avg": float(ear_avg),
            "mar": float(mar),
            "yaw": float(yaw),
            "pitch": float(pitch),
            "roll": float(roll),
        }

        # ── Delegate to shared engine for all windowed features ────────
        fv_dict = self._engine.update(roots)

        return FeatureVector(**fv_dict)


# ---------------------------------------------------------------------------
# Module constant
# ---------------------------------------------------------------------------

_NEUTRAL_ROOTS: dict[str, float] = {
    "ear_left": 0.35,
    "ear_right": 0.35,
    "ear_avg": 0.35,
    "mar": 0.0,
    "yaw": 0.0,
    "pitch": 0.0,
    "roll": 0.0,
}
