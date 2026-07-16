"""
Safety Monitor — điều phối cấp cao nhất, gộp DrowsinessDetector và
SeatbeltDetector, tôn trọng cờ bật/tắt và tần suất kiểm tra trong
AppRuntimeConfig.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.app_runtime_config import AppRuntimeConfig
from app.services.drowsiness_detector import DrowsinessDetector
from app.services.seatbelt_detector import SeatbeltDetector


class SafetyMonitor:

    def __init__(
        self,
        drowsiness_detector: DrowsinessDetector,
        seatbelt_detector: SeatbeltDetector,
        runtime_config: AppRuntimeConfig,
        seatbelt_warning_frame_threshold: int = 10,
    ) -> None:
        self.drowsiness_detector = drowsiness_detector
        self.seatbelt_detector = seatbelt_detector
        self.runtime_config = runtime_config

        # Số lần kiểm tra LIÊN TIẾP (không phải số frame thô, vì seatbelt
        # chỉ được check mỗi N frame) không thấy seatbelt trước khi thật
        # sự cảnh báo — tránh báo động giả khi model bỏ sót 1-2 lần detect.
        self.seatbelt_warning_frame_threshold = seatbelt_warning_frame_threshold
        self._no_seatbelt_streak = 0

        self._frame_index = 0
        self._last_seatbelt_result: dict | None = None

    def process(
        self,
        frame: np.ndarray,
        timestamp: float | None = None,
    ) -> tuple[np.ndarray, dict]:

        cfg = self.runtime_config

        drowsiness_result = None
        seatbelt_result = None

        # --- Drowsiness ---
        if cfg.drowsiness_enabled:
            frame, drowsiness_result = self.drowsiness_detector.process(
                frame, timestamp=timestamp
            )

        # --- Seatbelt (theo tần suất N frame) ---
        if cfg.seatbelt_enabled:

            should_check = (self._frame_index % cfg.seatbelt_check_every_n_frames == 0)

            if should_check:
                self._last_seatbelt_result = self.seatbelt_detector.detect(frame)

                if self._last_seatbelt_result["has_seatbelt"]:
                    self._no_seatbelt_streak = 0
                else:
                    self._no_seatbelt_streak += 1

            seatbelt_result = self._last_seatbelt_result

            is_warning = self._no_seatbelt_streak >= self.seatbelt_warning_frame_threshold

            frame = self._draw_seatbelt_overlay(frame, seatbelt_result, is_warning)

        self._frame_index += 1

        return frame, {
            "drowsiness": drowsiness_result,
            "seatbelt": seatbelt_result,
            "seatbelt_warning": (
                self._no_seatbelt_streak >= self.seatbelt_warning_frame_threshold
                if cfg.seatbelt_enabled else False
            ),
        }

    def _draw_seatbelt_overlay(
        self,
        frame: np.ndarray,
        seatbelt_result: dict | None,
        is_warning: bool,
    ) -> np.ndarray:

        if seatbelt_result is None:
            text = "Seatbelt: --"
            color = (150, 150, 150)
        elif seatbelt_result["has_seatbelt"]:
            conf = seatbelt_result["seatbelt_confidence"]
            text = f"Seatbelt: OK ({conf:.2f})"
            color = (0, 255, 0)
        elif is_warning:
            text = f"WARNING: NO SEATBELT ({self._no_seatbelt_streak})"
            color = (0, 0, 255)
        else:
            text = f"No seatbelt ({self._no_seatbelt_streak}/{self.seatbelt_warning_frame_threshold})"
            color = (0, 140, 255)

        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        x = frame.shape[1] - text_size[0] - 20

        cv2.putText(
            frame, text, (x, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2,
        )

        if is_warning:
            cv2.rectangle(
                frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 255), 4,
            )

        return frame