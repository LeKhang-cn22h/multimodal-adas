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
        padding_ratio: float = 0.35,
    ) -> None:
        # padding_ratio áp dụng trên CHIỀU RỘNG (ổn định),
        # không dùng chiều cao vì lúc ngậm miệng chiều cao gần như bằng 0.
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

        mouth_width = x2 - x1

        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        # Cạnh vuông = chiều rộng miệng + padding.
        # Dùng chiều rộng làm chuẩn vì nó ổn định (không co lại gần 0
        # như chiều cao khi ngậm miệng).
        side = int(mouth_width * (1 + self.padding_ratio))

        # Đảm bảo tối thiểu 1 kích thước hợp lý để không bị crop quá bé
        side = max(side, 40)

        half = side // 2

        nx1 = max(0, cx - half)
        ny1 = max(0, cy - half)

        nx2 = min(w, cx + half)
        ny2 = min(h, cy + half)

        if nx2 <= nx1 or ny2 <= ny1:
            return None

        return frame[ny1:ny2, nx1:nx2]