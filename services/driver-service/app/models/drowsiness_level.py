"""
Domain model: các mức độ buồn ngủ.

Đặt trong app/models/ vì đây là khái niệm nghiệp vụ (domain concept),
không phụ thuộc vào cách tính toán (CV/CNN) hay cách hiển thị.

TS-remove-headpose: chỉ còn 4 trạng thái — NORMAL, DROWSY, NO_FACE,
FACE_DETECTED_BUT_INVALID.  Head Pose đã bị loại bỏ hoàn toàn.
"""

from __future__ import annotations

from enum import Enum


class DrowsinessLevel(str, Enum):
    NORMAL = "NORMAL"
    DROWSY = "DROWSY"
    NO_FACE = "NO_FACE"
    FACE_DETECTED_BUT_INVALID = "FACE_DETECTED_BUT_INVALID"


LEVEL_DISPLAY: dict[DrowsinessLevel, dict] = {
    DrowsinessLevel.NORMAL: {"text": "AWAKE", "color": (0, 255, 0)},
    DrowsinessLevel.DROWSY: {"text": "DROWSY - WAKE UP!", "color": (0, 0, 255)},
    DrowsinessLevel.NO_FACE: {"text": "NO FACE DETECTED", "color": (0, 0, 255)},
    DrowsinessLevel.FACE_DETECTED_BUT_INVALID: {
        "text": "FACE DETECTED (INVALID)",
        "color": (0, 165, 255),
    },
}
