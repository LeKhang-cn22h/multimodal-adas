"""
Geometric Verifier — tính EAR (Eye Aspect Ratio) và MAR (Mouth Aspect Ratio)
từ landmark MediaPipe, dùng làm lớp XÁC THỰC BỔ SUNG cho CNN.

Mục đích: không thay thế CNN, mà làm "second opinion" — nếu 2 phương pháp
đồng thuận thì tăng độ tin cậy, nếu bất đồng thì có thể fallback về bên
đáng tin hơn hoặc log lại để debug sau.
"""

from __future__ import annotations

import numpy as np

# Landmark index MediaPipe FaceMesh cho EAR (6 điểm mỗi mắt, chuẩn dlib-style)
LEFT_EYE_EAR_POINTS = [33, 160, 158, 133, 153, 144]   # p1..p6
RIGHT_EYE_EAR_POINTS = [362, 385, 387, 263, 373, 380]  # p1..p6

# Landmark cho MAR
MOUTH_MAR_POINTS = {
    "top": 13,
    "bottom": 14,
    "left": 61,
    "right": 291,
}


def _dist(p1: tuple[int, int], p2: tuple[int, int]) -> float:
    return float(np.hypot(p1[0] - p2[0], p1[1] - p2[1]))


def compute_ear(landmarks: list[tuple[int, int]], eye_points: list[int]) -> float:
    p1, p2, p3, p4, p5, p6 = [landmarks[i] for i in eye_points]

    vertical_1 = _dist(p2, p6)
    vertical_2 = _dist(p3, p5)
    horizontal = _dist(p1, p4)

    if horizontal == 0:
        return 0.0

    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def compute_mar(landmarks: list[tuple[int, int]]) -> float:
    top = landmarks[MOUTH_MAR_POINTS["top"]]
    bottom = landmarks[MOUTH_MAR_POINTS["bottom"]]
    left = landmarks[MOUTH_MAR_POINTS["left"]]
    right = landmarks[MOUTH_MAR_POINTS["right"]]

    horizontal = _dist(left, right)

    if horizontal == 0:
        return 0.0

    return _dist(top, bottom) / horizontal


class GeometricVerifier:
    """
    Ngưỡng EAR/MAR mặc định là baseline tham khảo từ nghiên cứu gốc,
    NHƯNG BẮT BUỘC PHẢI CALIBRATE LẠI theo chính khuôn mặt/camera của bạn
    (xem hướng dẫn calibrate ở cuối file) vì EAR/MAR phụ thuộc tỷ lệ
    khuôn mặt từng người và góc đặt camera.
    """

    def __init__(
        self,
        ear_closed_threshold: float = 0.21,
        mar_yawn_threshold: float = 0.6,
    ) -> None:
        self.ear_closed_threshold = ear_closed_threshold
        self.mar_yawn_threshold = mar_yawn_threshold

    def verify_eye(self, landmarks: list[tuple[int, int]]) -> dict:
        left_ear = compute_ear(landmarks, LEFT_EYE_EAR_POINTS)
        right_ear = compute_ear(landmarks, RIGHT_EYE_EAR_POINTS)
        avg_ear = (left_ear + right_ear) / 2.0

        return {
            "left_ear": left_ear,
            "right_ear": right_ear,
            "avg_ear": avg_ear,
            "is_closed_geometric": avg_ear < self.ear_closed_threshold,
        }

    def verify_mouth(self, landmarks: list[tuple[int, int]]) -> dict:
        mar = compute_mar(landmarks)

        return {
            "mar": mar,
            "is_yawn_geometric": mar > self.mar_yawn_threshold,
        }


def combine_eye_signal(cnn_label: str, geometric_result: dict) -> str:
    """
    Kết hợp CNN + hình học theo chiến lược OR (ưu tiên an toàn/nhạy):
    chỉ cần 1 trong 2 báo CLOSED thì coi là CLOSED.

    Lý do dùng OR thay vì AND: mục tiêu là "tránh bỏ sót" (giảm false
    negative) như bạn nói, nên thà nhạy hơn (chấp nhận vài false positive,
    vốn đã được lọc bớt qua sliding window PERCLOS ở bước sau) còn hơn bỏ
    sót thật sự lúc tài xế nhắm mắt.
    """
    cnn_closed = cnn_label == "CLOSED"
    geo_closed = geometric_result["is_closed_geometric"]

    return "CLOSED" if (cnn_closed or geo_closed) else "OPEN"


def combine_mouth_signal(cnn_label: str, geometric_result: dict) -> str:
    cnn_yawn = cnn_label == "YAWN"
    geo_yawn = geometric_result["is_yawn_geometric"]

    return "YAWN" if (cnn_yawn or geo_yawn) else "NO_YAWN"