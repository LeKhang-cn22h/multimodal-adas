"""
Eye State Buffer — lọc nhiễu single-frame bằng sliding window theo THỜI GIAN.

Áp dụng PERCLOS (Percentage of Eye Closure) — chuẩn công nghiệp:
    PERCLOS = (thời gian mắt nhắm trong window) / (tổng thời gian window)

Blink bình thường: 100-400ms  -> PERCLOS thấp, không báo động.
Ngủ gật / nhắm mắt kéo dài: liên tục vượt ngưỡng -> báo động (microsleep).
"""

from __future__ import annotations

import time
from collections import deque

from app.core.drowsiness_config import DrowsinessThresholds, DEFAULT_THRESHOLDS


class EyeStateBuffer:

    def __init__(self, thresholds: DrowsinessThresholds = DEFAULT_THRESHOLDS) -> None:
        self.window_seconds = thresholds.eye_window_seconds
        self.perclos_drowsy_threshold = thresholds.perclos_drowsy_threshold
        self.microsleep_seconds = thresholds.microsleep_seconds

        self._history: deque[tuple[float, bool]] = deque()
        self._closed_streak_start: float | None = None

    def update(self, is_closed: bool, now: float | None = None) -> dict:
        """
        now: thời gian tham chiếu (giây). Mặc định dùng time.monotonic()
        (đúng cho webcam realtime). Với video file, PHẢI truyền
        now = frame_index / fps để buffer tính đúng theo timeline của
        video, không lệ thuộc tốc độ xử lý thực tế của máy.
        """
        if now is None:
            now = time.monotonic()

        self._history.append((now, is_closed))

        while self._history and now - self._history[0][0] > self.window_seconds:
            self._history.popleft()

        closed_duration = 0.0
        for i in range(1, len(self._history)):
            t_prev, closed_prev = self._history[i - 1]
            t_curr, _ = self._history[i]
            if closed_prev:
                closed_duration += t_curr - t_prev

        observed_span = (
            self._history[-1][0] - self._history[0][0]
            if len(self._history) > 1
            else 0.0
        )
        perclos = (closed_duration / observed_span) if observed_span > 0 else 0.0

        if is_closed:
            if self._closed_streak_start is None:
                self._closed_streak_start = now
            closed_streak_duration = now - self._closed_streak_start
        else:
            self._closed_streak_start = None
            closed_streak_duration = 0.0

        return {
            "perclos": perclos,
            "closed_streak_seconds": closed_streak_duration,
            "is_microsleep": closed_streak_duration >= self.microsleep_seconds,
            "is_perclos_drowsy": perclos >= self.perclos_drowsy_threshold,
        }