"""Windowed feature engineering — SHARED between runtime and training.

This module is imported by BOTH:
    - app/services/feature_service.py   (runtime, single continuous stream)
    - training/engineer_features.py     (offline, one instance per subject+scenario group)

A single source of truth for all 40-feature computation.

ADR-005: All sliding windows count by FRAME NUMBER (deque[float]),
not real-time timestamp.  max_size = window_seconds × FPS_ASSUMPTION.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# =============================================================================
#  SlidingWindowBuffer — fixed-size FIFO for one feature series
# =============================================================================


@dataclass
class SlidingWindowBuffer:
    """Fixed-size FIFO buffer counting frames, NOT real time (ADR-005).

    push(value) appends a float; the oldest value is auto-popped
    when the buffer reaches max_size.  No timestamp is stored.
    """

    max_size: int
    _buffer: deque[float] = field(default_factory=deque)

    def push(self, value: float) -> None:
        """Append a frame value; auto-pop oldest if buffer is full."""
        self._buffer.append(value)
        if len(self._buffer) > self.max_size:
            self._buffer.popleft()

    @property
    def values(self) -> list[float]:
        """Return a snapshot of the current buffer (oldest → newest)."""
        return list(self._buffer)

    @property
    def depth(self) -> int:
        """Number of frames currently buffered (0 .. max_size)."""
        return len(self._buffer)

    def is_full(self) -> bool:
        """True when the buffer has reached max_size."""
        return len(self._buffer) >= self.max_size

    def reset(self) -> None:
        """Clear all data (used by training when switching groups)."""
        self._buffer.clear()


# =============================================================================
#  WindowedFeatureEngineer  — 40-feature computation core
# =============================================================================


class WindowedFeatureEngineer:
    """Compute ALL 40 features from 7 root features per frame.

    DÙNG CHUNG bởi runtime (1 instance, no reset) và training
    (new instance per group, discard cold-start frames).

    Internal buffers:
        N_STAT  = 300 frames (10 s) → 28 statistical features
        N_PERCLOS = 900 frames (30 s) → PERCLOS + blink_rate
        N_VEL   =  30 frames ( 1 s) → 3 velocity features
    """

    def __init__(
        self,
        n_stat: int = 300,
        n_perclos: int = 900,
        n_vel: int = 30,
        ear_threshold: float = 0.22,
        fps: int = 30,
    ) -> None:
        self._ear_threshold: float = ear_threshold
        self._fps: int = fps

        # ── 7 buffers for statistical features (N_STAT) ───────────────
        self._ear_left_buf = SlidingWindowBuffer(max_size=n_stat)
        self._ear_right_buf = SlidingWindowBuffer(max_size=n_stat)
        self._ear_avg_buf = SlidingWindowBuffer(max_size=n_stat)
        self._mar_buf = SlidingWindowBuffer(max_size=n_stat)
        self._yaw_buf = SlidingWindowBuffer(max_size=n_stat)
        self._pitch_buf = SlidingWindowBuffer(max_size=n_stat)
        self._roll_buf = SlidingWindowBuffer(max_size=n_stat)

        # ── 1 large buffer for PERCLOS & blink_rate (N_PERCLOS) ───────
        self._perclos_buf = SlidingWindowBuffer(max_size=n_perclos)

        # ── 3 small buffers for velocity (N_VEL) ──────────────────────
        self._yaw_vel_buf = SlidingWindowBuffer(max_size=n_vel)
        self._pitch_vel_buf = SlidingWindowBuffer(max_size=n_vel)
        self._roll_vel_buf = SlidingWindowBuffer(max_size=n_vel)

        # Mapping for iteration: (buffer, prefix_name)
        self._stat_buffers: list[tuple[SlidingWindowBuffer, str]] = [
            (self._ear_left_buf, "ear_left"),
            (self._ear_right_buf, "ear_right"),
            (self._ear_avg_buf, "ear_avg"),
            (self._mar_buf, "mar"),
            (self._yaw_buf, "yaw"),
            (self._pitch_buf, "pitch"),
            (self._roll_buf, "roll"),
        ]

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def perclos_depth(self) -> int:
        """Number of frames in the PERCLOS buffer.

        Training scripts use this to decide cut-off (depth < N_PERCLOS →
        discard frame).  Runtime ignores this (expanding window behaviour).
        """
        return self._perclos_buf.depth

    # ------------------------------------------------------------------
    # Core update — called once per frame
    # ------------------------------------------------------------------

    def update(self, roots: dict[str, float]) -> dict[str, float]:
        """Push 7 root features to all buffers, compute 40 features.

        Args:
            roots:  dict with keys:
                        ear_left, ear_right, ear_avg,
                        mar, yaw, pitch, roll

        Returns:
            dict with 40 keys (exact column names matching the training CSV).
        """
        fv: dict[str, float] = {}

        # ── Push all root values ──────────────────────────────────────
        for buf, _name in self._stat_buffers:
            buf.push(roots[_name])
        self._perclos_buf.push(roots["ear_avg"])
        self._yaw_vel_buf.push(roots["yaw"])
        self._pitch_vel_buf.push(roots["pitch"])
        self._roll_vel_buf.push(roots["roll"])

        # ── A. Copy 7 root features directly ──────────────────────────
        for name in ("ear_left", "ear_right", "ear_avg", "mar", "yaw", "pitch", "roll"):
            fv[name] = float(roots[name])

        # ── B. 28 statistical features (N=300 backward, expanding window) ─
        for buf, name in self._stat_buffers:
            vals = np.array(buf.values, dtype=np.float64)
            fv[f"{name}_mean"] = float(np.mean(vals))
            fv[f"{name}_std"] = float(np.std(vals, ddof=1)) if len(vals) >= 2 else 0.0
            fv[f"{name}_min"] = float(np.min(vals))
            fv[f"{name}_max"] = float(np.max(vals))

        # ── C. PERCLOS (N=900 backward, expanding window) ─────────────
        perclos_vals = np.array(self._perclos_buf.values, dtype=np.float64)
        n_closed = int(np.sum(perclos_vals < self._ear_threshold))
        fv["perclos"] = (100.0 * n_closed / len(perclos_vals)) if perclos_vals.size > 0 else 0.0

        # ── D. Blink rate (N=900 backward, expanding window) ──────────
        fv["blink_rate"] = self._compute_blink_rate(perclos_vals)

        # ── E. 3 velocity features (N=30 backward, expanding window) ──
        fv["yaw_velocity"] = self._mean_abs_diff(self._yaw_vel_buf.values)
        fv["pitch_velocity"] = self._mean_abs_diff(self._pitch_vel_buf.values)
        fv["roll_velocity"] = self._mean_abs_diff(self._roll_vel_buf.values)

        return fv

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_blink_rate(self, ear_values: np.ndarray) -> float:
        """Count blink onsets in the PERCLOS window, return blinks/min.

        A blink *onset* occurs when EAR crosses BELOW the threshold
        (from above).  Consecutive onsets must be ≥ 5 frames apart
        to avoid double-counting oscillations at the boundary.
        """
        n_frames = ear_values.size
        if n_frames < 2:
            return 0.0

        blinks = 0
        last_blink_idx = -99  # far enough that first blink always counts

        for idx in range(1, n_frames):
            # crossing from above threshold to below
            if ear_values[idx - 1] >= self._ear_threshold and ear_values[idx] < self._ear_threshold:
                if idx - last_blink_idx >= 5:  # min 5-frame gap (~200 ms)
                    blinks += 1
                    last_blink_idx = idx

        window_sec = n_frames / self._fps
        if window_sec <= 0.0:
            return 0.0
        return float(blinks) / (window_sec / 60.0)

    @staticmethod
    def _mean_abs_diff(values: list[float]) -> float:
        """Mean absolute frame-to-frame difference × FPS → deg/s."""
        if len(values) < 2:
            return 0.0
        arr = np.array(values, dtype=np.float64)
        diffs = np.abs(np.diff(arr))
        return float(np.mean(diffs) * 30)  # FPS hardcoded per ADR-005 (30 fps)
