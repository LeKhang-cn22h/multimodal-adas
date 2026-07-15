"""
Drowsiness Rule Engine.

Quyết định trạng thái buồn ngủ dựa trên:

- Có phát hiện khuôn mặt hay không
- ROI (mắt/miệng) có crop được không
- PERCLOS
- Microsleep
- Yawn

TS-remove-headpose: không còn Head Pose. Gộp tất cả trạng thái buồn ngủ
thành DROWSY duy nhất.
"""

from __future__ import annotations

from app.models.drowsiness_level import DrowsinessLevel


class DrowsinessRuleEngine:

    def decide(
        self,
        face_detected: bool,
        crop_valid: bool,
        eye_buffer_result: dict | None,
        mouth_buffer_result: dict | None,
    ) -> DrowsinessLevel:

        if not face_detected:
            return DrowsinessLevel.NO_FACE

        if not crop_valid:
            return DrowsinessLevel.FACE_DETECTED_BUT_INVALID

        if (
            eye_buffer_result is not None
            and eye_buffer_result.get("is_microsleep")
        ):
            return DrowsinessLevel.DROWSY

        if (
            eye_buffer_result is not None
            and eye_buffer_result.get("is_perclos_drowsy")
        ):
            return DrowsinessLevel.DROWSY

        if (
            mouth_buffer_result is not None
            and mouth_buffer_result.get("is_real_yawn")
        ):
            return DrowsinessLevel.DROWSY

        return DrowsinessLevel.NORMAL
