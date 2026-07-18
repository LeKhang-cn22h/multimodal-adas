"""
Driver Selector.

Khi có nhiều khuôn mặt trong khung hình, chọn đúng khuôn mặt của TÀI XẾ
để phân tích, tránh báo động nhầm do hành khách chớp mắt/ngáp.
"""

from __future__ import annotations

import numpy as np

from app.core.drowsiness_config import DrowsinessThresholds, DEFAULT_THRESHOLDS


class DriverSelector:

    def __init__(self, thresholds: DrowsinessThresholds = DEFAULT_THRESHOLDS) -> None:
        self.expected_region = thresholds.driver_expected_region
        self.stability_weight = thresholds.driver_stability_weight
        self._last_selected_center: tuple[float, float] | None = None

    def _face_bbox(self, landmarks: list[tuple[int, int]]) -> tuple[int, int, int, int]:
        pts = np.array(landmarks, dtype=np.int32)
        x1, y1 = pts[:, 0].min(), pts[:, 1].min()
        x2, y2 = pts[:, 0].max(), pts[:, 1].max()
        return x1, y1, x2, y2

    def select(
        self,
        frame_shape: tuple[int, int],
        all_landmarks: list[list[tuple[int, int]]],
    ) -> list[tuple[int, int]] | None:

        if not all_landmarks:
            self._last_selected_center = None
            return None

        if len(all_landmarks) == 1:
            landmarks = all_landmarks[0]
            x1, y1, x2, y2 = self._face_bbox(landmarks)
            self._last_selected_center = ((x1 + x2) / 2, (y1 + y2) / 2)
            return landmarks

        h, w = frame_shape[:2]
        scored: list[tuple[float, list[tuple[int, int]]]] = []

        for landmarks in all_landmarks:
            x1, y1, x2, y2 = self._face_bbox(landmarks)
            area = (x2 - x1) * (y2 - y1)
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

            score = area

            if self.expected_region is not None:
                xr, yr = cx / w, cy / h
                rx1, ry1, rx2, ry2 = self.expected_region
                if rx1 <= xr <= rx2 and ry1 <= yr <= ry2:
                    score *= 1.5

            if self._last_selected_center is not None:
                dist = np.hypot(cx - self._last_selected_center[0], cy - self._last_selected_center[1])
                proximity_score = max(0.0, 1.0 - dist / w)
                score *= (1.0 + self.stability_weight * proximity_score)

            scored.append((score, landmarks))

        scored.sort(key=lambda item: item[0], reverse=True)
        best_landmarks = scored[0][1]

        x1, y1, x2, y2 = self._face_bbox(best_landmarks)
        self._last_selected_center = ((x1 + x2) / 2, (y1 + y2) / 2)

        return best_landmarks