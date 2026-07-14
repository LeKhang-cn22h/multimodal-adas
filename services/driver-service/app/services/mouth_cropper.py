"""
Mouth Cropper.

Input
-----
Frame (OpenCV BGR)
468 FaceMesh landmarks

Output
------
Mouth ROI (BGR)

Không resize.
Không normalize.
"""

from __future__ import annotations

import numpy as np


# MediaPipe FaceMesh
MOUTH = [
    61, 291,
    13, 14,
    78, 308,
    81, 311,
    82, 312,
    87, 317,
    88, 318,
    95, 324,
]


class MouthCropper:

    def __init__(
        self,
        padding_ratio: float = 0.25,
    ) -> None:

        self.padding_ratio = padding_ratio

    def crop(
        self,
        frame: np.ndarray,
        landmarks: list[tuple[int, int]],
    ) -> np.ndarray | None:

        h, w = frame.shape[:2]

        pts = np.array(
            [landmarks[i] for i in MOUTH],
            dtype=np.int32,
        )

        x1 = pts[:, 0].min()
        y1 = pts[:, 1].min()

        x2 = pts[:, 0].max()
        y2 = pts[:, 1].max()

        pad_x = int((x2 - x1) * self.padding_ratio)
        pad_y = int((y2 - y1) * self.padding_ratio)

        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)

        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)

        if x2 <= x1 or y2 <= y1:
            return None

        return frame[y1:y2, x1:x2]