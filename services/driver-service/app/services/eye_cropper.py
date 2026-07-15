from __future__ import annotations

import numpy as np


LEFT_EYE = [
    33, 133, 160, 158, 153, 144,
    163, 7, 246, 161, 159, 157, 173
]

RIGHT_EYE = [
    362, 263, 387, 385, 373, 380,
    390, 249, 466, 388, 386, 384, 398
]


class EyeCropper:

    def __init__(self, padding_ratio: float = 0.15) -> None:
        self.padding_ratio = padding_ratio

    def _crop_one(self, frame, landmarks, indices):

        h, w = frame.shape[:2]

        pts = np.array([landmarks[i] for i in indices], dtype=np.int32)

        x1, y1 = pts[:, 0].min(), pts[:, 1].min()
        x2, y2 = pts[:, 0].max(), pts[:, 1].max()

        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        side = max(x2 - x1, y2 - y1)
        side = int(side * (1 + self.padding_ratio))
        half = side // 2

        x1, y1 = max(0, cx - half), max(0, cy - half)
        x2, y2 = min(w, cx + half), min(h, cy + half)

        if x2 <= x1 or y2 <= y1:
            return None

        return frame[y1:y2, x1:x2]

    def crop_left(self, frame, landmarks):
        return self._crop_one(frame, landmarks, LEFT_EYE)

    def crop_right(self, frame, landmarks):
        return self._crop_one(frame, landmarks, RIGHT_EYE)