"""
Mouth State Buffer — lọc ngáp (yawn) khỏi nói chuyện (talking).

- Ngáp: miệng mở LIÊN TỤC, kéo dài (thường 2-6 giây), ít transition.
- Nói chuyện: miệng mở/đóng NHIỀU LẦN, mỗi lần rất ngắn, tần suất cao.
"""

from __future__ import annotations

import time
from collections import deque

from app.core.drowsiness_config import DrowsinessThresholds, DEFAULT_THRESHOLDS


class MouthStateBuffer:

    def __init__(self, thresholds: DrowsinessThresholds = DEFAULT_THRESHOLDS) -> None:
        self.window_seconds = thresholds.mouth_window_seconds
        self.yawn_min_duration = thresholds.yawn_min_duration
        self.talking_transition_threshold = thresholds.talking_transition_threshold

        self._history: deque[tuple[float, bool]] = deque()
        self._open_streak_start: float | None = None

    def update(self, is_yawn: bool, now: float | None = None) -> dict:
        """
        now: thời gian tham chiếu (giây). Mặc định dùng time.monotonic()
        (đúng cho webcam realtime). Với video file, PHẢI truyền
        now = frame_index / fps để buffer tính đúng theo timeline của
        video, không lệ thuộc tốc độ xử lý thực tế của máy.
        """
        if now is None:
            now = time.monotonic()

        self._history.append((now, is_yawn))

        while self._history and now - self._history[0][0] > self.window_seconds:
            self._history.popleft()

        transitions = 0
        for i in range(1, len(self._history)):
            if self._history[i][1] != self._history[i - 1][1]:
                transitions += 1

        is_talking = transitions >= self.talking_transition_threshold

        if is_yawn:
            if self._open_streak_start is None:
                self._open_streak_start = now
            open_streak_duration = now - self._open_streak_start
        else:
            self._open_streak_start = None
            open_streak_duration = 0.0

        is_real_yawn = (
            open_streak_duration >= self.yawn_min_duration
            and not is_talking
        )

        return {
            "open_streak_seconds": open_streak_duration,
            "transitions": transitions,
            "is_talking": is_talking,
            "is_real_yawn": is_real_yawn,
        }