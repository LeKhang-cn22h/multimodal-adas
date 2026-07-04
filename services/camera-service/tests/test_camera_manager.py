"""Unit tests for CameraManager."""

import threading
import time

import pytest


class TestCameraManager:
    @pytest.fixture
    def camera_manager(self, mocker):
        mocker.patch("cv2.VideoCapture")
        mocker.patch("cv2.imencode")
        from app.services.camera_manager import CameraManager

        return CameraManager()

    def test_init_sets_config(self, camera_manager):
        assert camera_manager._jpeg_quality == 85
        assert camera_manager._target_width == 640
        assert camera_manager._target_height == 480

    def test_is_running_initially_false(self, camera_manager):
        assert camera_manager.is_running is False

    def test_frame_id_initially_zero(self, camera_manager):
        assert camera_manager.frame_id == 0

    def test_latest_jpeg_initially_none(self, camera_manager):
        assert camera_manager.latest_jpeg is None

    def test_latest_frame_initially_none(self, camera_manager):
        assert camera_manager.latest_frame is None

    def test_set_on_frame_callback(self, camera_manager):
        calls = []

        def callback(jpeg_bytes, frame_id, timestamp):
            calls.append((jpeg_bytes, frame_id, timestamp))

        camera_manager.set_on_frame_callback(callback)
        assert camera_manager._on_frame_callback is callback

    def test_start_creates_thread(self, camera_manager, mocker):
        mocker.patch.object(camera_manager, "_try_open_camera")
        camera_manager.start()
        assert camera_manager.is_running is True
        camera_manager.stop()

    def test_stop_joins_thread(self, camera_manager, mocker):
        mocker.patch.object(camera_manager, "_try_open_camera")
        camera_manager.start()
        camera_manager.stop()
        assert not camera_manager.is_running

    def test_double_start_warns(self, camera_manager, mocker):
        mocker.patch.object(camera_manager, "_try_open_camera")
        mock_warn = mocker.patch.object(camera_manager._logger, "warning")
        camera_manager.start()
        camera_manager.start()
        mock_warn.assert_called()
        camera_manager.stop()

    def test_get_stats(self, camera_manager):
        stats = camera_manager.get_stats()
        assert "uptime" in stats
        assert "total_frames" in stats
        assert "camera_fps" in stats

    def test_try_open_camera_handles_exception(self, camera_manager, mocker):
        mock_cv2 = mocker.patch("cv2.VideoCapture")
        mock_cv2.side_effect = Exception("test error")
        mock_logger = mocker.patch.object(camera_manager._logger, "exception")

        camera_manager._try_open_camera()
        mock_logger.assert_called_once()
        assert camera_manager._capture is None

    def test_width_height_properties(self, camera_manager):
        assert isinstance(camera_manager.width, int)
        assert isinstance(camera_manager.height, int)

    def test_fps_property(self, camera_manager):
        assert camera_manager.fps == 0.0
