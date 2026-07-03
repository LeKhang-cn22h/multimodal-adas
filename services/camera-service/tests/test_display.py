"""Unit tests for DisplayOverlay."""

import numpy as np
import pytest

from app.services.display import DisplayOverlay
from app.models.messages import DriverResultMessage, SeatbeltResultMessage


class TestDisplayOverlay:
    @pytest.fixture
    def blank_frame(self):
        return np.zeros((480, 640, 3), dtype=np.uint8)

    @pytest.fixture
    def display(self, mocker):
        mock_camera = mocker.MagicMock()
        return DisplayOverlay(mock_camera)

    def test_update_driver_result(self, display):
        result = DriverResultMessage(
            frame_id=1, timestamp=1.0, sleepy=True, confidence=0.9
        )
        display.update_driver_result(result)
        assert display._driver_result is not None
        assert display._driver_result.sleepy is True

    def test_update_seatbelt_result(self, display):
        result = SeatbeltResultMessage(
            frame_id=1, timestamp=1.0, seatbelt=True, confidence=0.8
        )
        display.update_seatbelt_result(result)
        assert display._seatbelt_result is not None
        assert display._seatbelt_result.seatbelt is True

    def test_draw_hud_sleepy_yes(self, display, blank_frame):
        display.update_driver_result(
            DriverResultMessage(frame_id=1, timestamp=1.0, sleepy=True, confidence=0.9)
        )
        result = display._draw_hud(blank_frame.copy())
        assert result.shape == (480, 640, 3)
        assert isinstance(result, np.ndarray)

    def test_draw_hud_sleepy_no(self, display, blank_frame):
        display.update_driver_result(
            DriverResultMessage(frame_id=1, timestamp=1.0, sleepy=False, confidence=0.1)
        )
        result = display._draw_hud(blank_frame.copy())
        assert result.shape == blank_frame.shape

    def test_draw_hud_seatbelt_yes(self, display, blank_frame):
        display.update_seatbelt_result(
            SeatbeltResultMessage(frame_id=1, timestamp=1.0, seatbelt=True, confidence=0.9)
        )
        result = display._draw_hud(blank_frame.copy())
        assert result.shape == blank_frame.shape

    def test_draw_hud_no_results(self, display, blank_frame):
        result = display._draw_hud(blank_frame.copy())
        assert result.shape == blank_frame.shape

    def test_draw_hud_both_results(self, display, blank_frame):
        display.update_driver_result(
            DriverResultMessage(frame_id=1, timestamp=1.0, sleepy=False, confidence=0.2)
        )
        display.update_seatbelt_result(
            SeatbeltResultMessage(frame_id=1, timestamp=1.0, seatbelt=True, confidence=0.8)
        )
        result = display._draw_hud(blank_frame.copy())
        assert result.shape == blank_frame.shape

    def test_put_text_bg(self, display, blank_frame):
        result = display._put_text_bg(blank_frame.copy(), "TEST", (10, 30))
        assert result is None

    def test_stop_closes_window(self, display, mocker):
        mock_destroy = mocker.patch("cv2.destroyAllWindows")
        display.stop()
        mock_destroy.assert_called_once()
