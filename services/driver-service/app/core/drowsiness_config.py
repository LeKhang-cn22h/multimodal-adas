"""
Các ngưỡng (threshold) dùng cho logic phát hiện buồn ngủ.

Gom tại đây để dễ tune mà không phải sửa code logic bên trong
các service/temporal/decision.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DrowsinessThresholds:

    # --- Eye sliding window (PERCLOS + microsleep) ---
    eye_window_seconds: float = 3.0
    perclos_drowsy_threshold: float = 0.5
    microsleep_seconds: float = 1.5

    # --- Mouth sliding window (yawn vs talking) ---
    mouth_window_seconds: float = 4.0
    yawn_min_duration: float = 1.5
    talking_transition_threshold: int = 3

    no_face_alert_seconds: float = 2.0

    # --- Driver selector (multi-face) ---
    # (x_min_ratio, y_min_ratio, x_max_ratio, y_max_ratio) theo % khung hình.
    # None nghĩa là không ưu tiên vùng nào, chỉ chọn theo mặt lớn nhất.
    driver_expected_region: tuple[float, float, float, float] | None = None
    driver_stability_weight: float = 0.3


DEFAULT_THRESHOLDS = DrowsinessThresholds()