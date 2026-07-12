"""RuleBasedClassifier — 4-level PERCLOS-based drowsiness classification.

Implements IClassifier with the algorithm from REQ AC-3.5:
    Dangerous ← PERCLOS > 40% OR microsleep ≥ 2 s
    Drowsy    ← PERCLOS 25-40% OR head-tilt ≥ 3 s
    Tired     ← PERCLOS 15-25% OR yawn ≥ 3 / 60 s
    Awake     ← otherwise

All thresholds are read from core/config.py — no hardcoded values.
"""

import time
from collections import deque
from typing import Optional

from app.core.config import get_settings
from app.schemas.classification_result import ClassificationResult
from app.services.classifier_interface import IClassifier
from app.services.feature_service import FeatureVector


class RuleBasedClassifier(IClassifier):
    """4-level rule-based drowsiness classifier.

    Maintains internal state across frames:
        - Yawn counter (MAR above threshold within a 60 s window)
        - Head-tilt duration (continuous abnormal pitch/yaw)
        - Microsleep duration (continuous EAR below threshold)

    Classification is evaluated top-down (most severe first), with
    OR logic between PERCLOS ranges and auxiliary conditions.
    """

    def __init__(self) -> None:
        settings = get_settings()

        # ── Thresholds from config ─────────────────────────────────
        self._perclos_awake_max: float = settings.PERCLOS_AWAKE_MAX      # 15
        self._perclos_tired_max: float = settings.PERCLOS_TIRED_MAX      # 25
        self._perclos_drowsy_max: float = settings.PERCLOS_DROWSY_MAX    # 40
        self._mar_threshold: float = settings.MAR_THRESHOLD              # 0.6
        self._yawn_count_threshold: int = settings.YAWN_COUNT_THRESHOLD  # 3
        self._yawn_window_seconds: int = settings.YAWN_WINDOW_SECONDS    # 60
        self._head_pose_pitch: float = settings.HEAD_POSE_PITCH_THRESHOLD  # 20
        self._head_pose_yaw: float = settings.HEAD_POSE_YAW_THRESHOLD    # 25
        self._head_tilt_duration: float = settings.HEAD_TILT_DURATION_SECONDS  # 3
        self._microsleep_ear: float = settings.EAR_THRESHOLD             # 0.22
        self._microsleep_duration: float = settings.MICROSLEEP_DURATION_SECONDS  # 2

        # ── Internal state ─────────────────────────────────────────
        self._mar_timestamps: deque[float] = deque()
        self._head_tilt_start: Optional[float] = None
        self._microsleep_start: Optional[float] = None

    # ------------------------------------------------------------------
    # IClassifier implementation
    # ------------------------------------------------------------------

    @property
    def method(self) -> str:
        return "rule_based"

    def classify(self, features: FeatureVector) -> ClassificationResult:
        """Classify one 40-feature vector → ClassificationResult."""
        now = time.time()

        # ── 1. Extract key features ─────────────────────────────────
        perclos = features.perclos
        ear_avg = features.ear_avg
        mar = features.mar
        yaw = features.yaw
        pitch = features.pitch

        # ── 2. Update internal state ─────────────────────────────────
        yawn_count = self._update_yawn_state(mar, now)
        head_tilt_dur = self._update_head_tilt_state(yaw, pitch, now)
        microsleep_dur = self._update_microsleep_state(ear_avg, now)

        # ── 3. Classify (top-down, OR logic) ─────────────────────────
        level: str
        score: int
        confidence: float

        # CHECK 1 — Dangerous: PERCLOS > 40% OR microsleep ≥ 2 s
        if microsleep_dur >= self._microsleep_duration:
            level = "Dangerous"
            score = 100
            confidence = min(1.0, microsleep_dur / self._microsleep_duration)

        elif perclos > self._perclos_drowsy_max:
            level = "Dangerous"
            score = min(100, int(perclos * 2.5))
            confidence = min(1.0, perclos / 60.0)

        # CHECK 2 — Drowsy: PERCLOS 25-40% OR head-tilt ≥ 3 s
        elif perclos > self._perclos_tired_max:
            level = "Drowsy"
            score = 50 + int(
                (perclos - self._perclos_tired_max)
                / (self._perclos_drowsy_max - self._perclos_tired_max)
                * 25
            )
            confidence = 0.6 + (
                (perclos - self._perclos_tired_max)
                / (self._perclos_drowsy_max - self._perclos_tired_max)
            ) * 0.3

        elif head_tilt_dur >= self._head_tilt_duration:
            level = "Drowsy"
            score = 60  # midpoint of Drowsy range
            confidence = min(0.85, head_tilt_dur / (self._head_tilt_duration * 2))

        # CHECK 3 — Tired: PERCLOS 15-25% OR yawn ≥ 3 / 60 s
        elif perclos > self._perclos_awake_max:
            level = "Tired"
            score = 25 + int(
                (perclos - self._perclos_awake_max)
                / (self._perclos_tired_max - self._perclos_awake_max)
                * 25
            )
            confidence = 0.3 + (
                (perclos - self._perclos_awake_max)
                / (self._perclos_tired_max - self._perclos_awake_max)
            ) * 0.3

        elif yawn_count >= self._yawn_count_threshold:
            level = "Tired"
            score = 35  # midpoint of Tired range
            confidence = min(0.80, yawn_count / (self._yawn_count_threshold * 2))

        # CHECK 4 — Awake: default
        else:
            level = "Awake"
            score = int(perclos / self._perclos_awake_max * 25)
            confidence = 0.7 + (1.0 - perclos / self._perclos_awake_max) * 0.3

        # Clamp to valid ranges
        score = max(0, min(100, score))
        confidence = max(0.0, min(1.0, confidence))

        return ClassificationResult(
            fatigue_score=score,
            fatigue_level=level,  # type: ignore[arg-type]
            confidence=round(confidence, 4),
            classification_method="rule_based",
            features={
                "ear": round(ear_avg, 4),
                "perclos": round(perclos, 4),
                "mar": round(mar, 4),
                "yaw": round(yaw, 4),
                "pitch": round(pitch, 4),
                "roll": round(features.roll, 4),
            },
        )

    # ------------------------------------------------------------------
    # State update helpers
    # ------------------------------------------------------------------

    def _update_yawn_state(self, mar: float, now: float) -> int:
        """Record a yawn event if MAR exceeds threshold; evict old entries.

        Returns:
            Number of yawn events within the configured window.
        """
        if mar > self._mar_threshold:
            self._mar_timestamps.append(now)

        # Evict timestamps older than the yawn window
        cutoff = now - self._yawn_window_seconds
        while self._mar_timestamps and self._mar_timestamps[0] < cutoff:
            self._mar_timestamps.popleft()

        return len(self._mar_timestamps)

    def _update_head_tilt_state(
        self, yaw: float, pitch: float, now: float
    ) -> float:
        """Track continuous duration of abnormal head pose.

        Returns:
            Seconds since head tilt began, or 0.0 if pose is normal.
        """
        tilted = (
            abs(pitch) > self._head_pose_pitch
            or abs(yaw) > self._head_pose_yaw
        )
        if tilted:
            if self._head_tilt_start is None:
                self._head_tilt_start = now
            return now - self._head_tilt_start
        else:
            self._head_tilt_start = None
            return 0.0

    def _update_microsleep_state(self, ear_avg: float, now: float) -> float:
        """Track continuous duration of eyes-closed (EAR below threshold).

        Returns:
            Seconds since microsleep began, or 0.0 if eyes are open.
        """
        closed = ear_avg < self._microsleep_ear
        if closed:
            if self._microsleep_start is None:
                self._microsleep_start = now
            return now - self._microsleep_start
        else:
            self._microsleep_start = None
            return 0.0
