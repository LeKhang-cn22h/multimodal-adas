"""Unit tests for EAR calculation."""

import numpy as np
import pytest


class MockLandmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class TestCalculateEAR:
    def _make_landmarks(self, points):
        return [MockLandmark(x, y) for x, y in points]

    def test_normal_eye(self):
        from app.utils.ear import calculate_ear

        landmarks = self._make_landmarks([
            (0.4, 0.5), (0.42, 0.48), (0.43, 0.47),
            (0.45, 0.5), (0.43, 0.53), (0.42, 0.52),
        ])
        ear = calculate_ear(landmarks, [0, 1, 2, 3, 4, 5])
        assert 0.10 < ear < 0.50

    def test_closed_eye(self):
        from app.utils.ear import calculate_ear

        landmarks = self._make_landmarks([
            (0.4, 0.5), (0.42, 0.498), (0.43, 0.497),
            (0.45, 0.5), (0.43, 0.503), (0.42, 0.502),
        ])
        ear = calculate_ear(landmarks, [0, 1, 2, 3, 4, 5])
        assert ear < 0.15

    def test_left_eye_indices(self):
        from app.utils.ear import LEFT_EYE

        assert len(LEFT_EYE) == 6
        assert LEFT_EYE == [33, 160, 158, 133, 153, 144]

    def test_right_eye_indices(self):
        from app.utils.ear import RIGHT_EYE

        assert len(RIGHT_EYE) == 6
        assert RIGHT_EYE == [362, 385, 387, 263, 373, 380]

    def test_returns_float(self):
        from app.utils.ear import calculate_ear

        landmarks = self._make_landmarks([
            (0.4, 0.5), (0.42, 0.48), (0.43, 0.47),
            (0.45, 0.5), (0.43, 0.53), (0.42, 0.52),
        ])
        ear = calculate_ear(landmarks, [0, 1, 2, 3, 4, 5])
        assert isinstance(ear, float)


class TestFatigueDetector:
    def test_decode_jpeg(self, mocker):
        from app.services.fatigue_detector import FatigueDetector

        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock(
            EAR_THRESHOLD=0.22,
            DROWSY_FRAMES=60,
            MODEL_PATH="",
            SLIDING_WINDOW_SIZE=90,
        )

        import cv2
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", img)
        jpeg_data = jpeg_bytes.tobytes()

        result = FatigueDetector._decode_jpeg(jpeg_data)
        assert result is not None
        assert result.shape == (100, 100, 3)

    def test_decode_jpeg_invalid(self):
        from app.services.fatigue_detector import FatigueDetector

        result = FatigueDetector._decode_jpeg(b"not a valid jpeg")
        assert result is None

    def test_build_result(self, mocker):
        from app.services.fatigue_detector import FatigueDetector

        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock(
            EAR_THRESHOLD=0.22,
            DROWSY_FRAMES=60,
            MODEL_PATH="",
            SLIDING_WINDOW_SIZE=90,
        )

        detector = FatigueDetector()
        result = detector._build_result(42, 100.0, True, 0.95, 0.0)
        assert result["frame_id"] == 42
        assert result["timestamp"] == 100.0
        assert result["sleepy"] is True
        assert result["confidence"] == 0.95

    def test_load_model_creates_landmarker(self, mocker):
        from app.services.fatigue_detector import FatigueDetector

        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock(
            EAR_THRESHOLD=0.22,
            DROWSY_FRAMES=60,
            MODEL_PATH="test.task",
            SLIDING_WINDOW_SIZE=90,
        )
        mock_tasks = mocker.patch("app.services.fatigue_detector.FaceLandmarker")
        mock_landmarker = mocker.MagicMock()
        mock_tasks.create_from_options.return_value = mock_landmarker

        detector = FatigueDetector()
        detector.load_model()

        assert detector.is_loaded is True
        mock_tasks.create_from_options.assert_called_once()

    def test_stats_defaults(self, mocker):
        from app.services.fatigue_detector import FatigueDetector

        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock(
            EAR_THRESHOLD=0.22,
            DROWSY_FRAMES=60,
            MODEL_PATH="",
            SLIDING_WINDOW_SIZE=90,
        )

        detector = FatigueDetector()
        stats = detector.get_stats()
        assert "uptime" in stats
        assert "total_frames" in stats
        assert "drowsy_events" in stats
        assert stats["total_frames"] == 0
        assert stats["drowsy_events"] == 0
