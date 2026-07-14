"""
Eye Cropper.

Input
-----
Frame (BGR)
468 FaceMesh landmarks

Output
------
Eye ROI (BGR)

Không resize.
Không normalize.
Không chạy CNN.
"""

from __future__ import annotations

import cv2
import numpy as np


# MediaPipe FaceMesh indices

LEFT_EYE = [
    33, 133, 160, 158, 153, 144,
    163, 7, 246, 161, 159, 157, 173
]

RIGHT_EYE = [
    362, 263, 387, 385, 373, 380,
    390, 249, 466, 388, 386, 384, 398
]


class EyeCropper:

    def __init__(
        self,
        padding_ratio: float = 0.20,
    ) -> None:

        self.padding_ratio = padding_ratio

    def _bbox(
        self,
        landmarks,
        indices,
    ):

        pts = np.array(
            [landmarks[i] for i in indices],
            dtype=np.int32,
        )

        x1 = pts[:, 0].min()
        y1 = pts[:, 1].min()

        x2 = pts[:, 0].max()
        y2 = pts[:, 1].max()

        return x1, y1, x2, y2

    def crop(
        self,
        frame: np.ndarray,
        landmarks,
    ) -> np.ndarray | None:

        h, w = frame.shape[:2]

        lx1, ly1, lx2, ly2 = self._bbox(
            landmarks,
            LEFT_EYE,
        )

        rx1, ry1, rx2, ry2 = self._bbox(
            landmarks,
            RIGHT_EYE,
        )

        x1 = min(lx1, rx1)
        y1 = min(ly1, ry1)

        x2 = max(lx2, rx2)
        y2 = max(ly2, ry2)

        pad_x = int((x2 - x1) * self.padding_ratio)
        pad_y = int((y2 - y1) * self.padding_ratio)

        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)

        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)

        if x2 <= x1 or y2 <= y1:
            return None

        roi = frame[
            y1:y2,
            x1:x2,
        ]

        return roi