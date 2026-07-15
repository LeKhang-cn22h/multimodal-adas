"""
Runtime Config — khác với DrowsinessThresholds (cố định lúc khởi tạo),
đây là các cờ CÓ THỂ THAY ĐỔI KHI ĐANG CHẠY (qua trackbar/phím tắt),
nên dùng class thường (mutable), không dùng frozen dataclass.
"""

from __future__ import annotations


class AppRuntimeConfig:

    def __init__(
        self,
        drowsiness_enabled: bool = True,
        seatbelt_enabled: bool = True,
        seatbelt_check_every_n_frames: int = 10,
    ) -> None:
        self.drowsiness_enabled = drowsiness_enabled
        self.seatbelt_enabled = seatbelt_enabled

        # Seatbelt không cần check mỗi frame (dây an toàn không đổi
        # trạng thái nhanh như mắt/miệng), nên mặc định kiểm tra
        # 1 lần mỗi N frame để tiết kiệm tài nguyên (YOLO nặng hơn
        # nhiều so với 2 CNN nhỏ của eye/mouth).
        self.seatbelt_check_every_n_frames = max(1, seatbelt_check_every_n_frames)