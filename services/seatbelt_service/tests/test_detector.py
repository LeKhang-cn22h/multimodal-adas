"""Unit tests for SeatbeltDetector."""

import numpy as np
import pytest


class TestSeatbeltDetector:
    @pytest.fixture
    def detector(self, mocker):
        mock_settings = mocker.patch("app.services.seatbelt_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock(
            MODEL_PATH="best.pt",
            CONFIDENCE_THRESHOLD=0.3,
            WARNING_FRAMES=10,
        )
        from app.services.seatbelt_detector import SeatbeltDetector

        return SeatbeltDetector()

    def test_decode_jpeg_valid(self, detector):
        import cv2

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", img)
        jpeg_data = jpeg_bytes.tobytes()

        result = detector._decode_jpeg(jpeg_data)
        assert result is not None
        assert result.shape == (100, 100, 3)

    def test_decode_jpeg_invalid(self, detector):
        result = detector._decode_jpeg(b"not a valid jpeg")
        assert result is None

    def test_build_result_seatbelt_true(self, detector):
        result = detector._build_result(42, 100.0, True, 0.88)
        assert result["frame_id"] == 42
        assert result["timestamp"] == 100.0
        assert result["seatbelt"] is True
        assert result["confidence"] == 0.88

    def test_build_result_seatbelt_false(self, detector):
        result = detector._build_result(99, 200.0, False, 0.1)
        assert result["seatbelt"] is False
        assert result["confidence"] == 0.1

    def test_update_stats_seatbelt_ok_resets_streak(self, detector):
        detector._no_seatbelt_streak = 5
        detector._update_stats(has_seatbelt=True, inference_ms=50.0)
        assert detector._no_seatbelt_streak == 0
        assert detector._seatbelt_ok == 1
        assert detector._total_checks == 1

    def test_update_stats_seatbelt_missing_increments_streak(self, detector):
        detector._no_seatbelt_streak = 3
        detector._update_stats(has_seatbelt=False, inference_ms=40.0)
        assert detector._no_seatbelt_streak == 4
        assert detector._seatbelt_missing == 1
        assert detector._total_checks == 1

    def test_update_stats_tracks_inference_time(self, detector):
        detector._update_stats(has_seatbelt=True, inference_ms=30.0)
        detector._update_stats(has_seatbelt=False, inference_ms=50.0)
        assert len(detector._inference_times) == 2
        assert detector._inference_times == [30.0, 50.0]

    def test_get_latest_result_no_streak(self, detector):
        result = detector.get_latest_result()
        assert result["seatbelt_detected"] is True
        assert result["no_seatbelt_streak"] == 0
        assert result["warning"] is False

    def test_get_latest_result_with_streak(self, detector):
        detector._no_seatbelt_streak = 5
        result = detector.get_latest_result()
        assert result["seatbelt_detected"] is False
        assert result["no_seatbelt_streak"] == 5
        assert result["warning"] is False

    def test_get_latest_result_warning(self, detector):
        detector._no_seatbelt_streak = 10
        result = detector.get_latest_result()
        assert result["warning"] is True

    def test_get_stats_defaults(self, detector):
        stats = detector.get_stats()
        assert stats["total_checks"] == 0
        assert stats["seatbelt_ok_count"] == 0
        assert stats["seatbelt_missing_count"] == 0
        assert stats["avg_inference_ms"] == 0.0

    def test_class_names(self):
        from app.services.seatbelt_detector import CLASS_NAMES, SEATBELT_CLASS_ID

        assert SEATBELT_CLASS_ID == 6
        assert CLASS_NAMES[6] == "seatbelt"
        assert CLASS_NAMES[0] == "cell phone"
        assert len(CLASS_NAMES) == 7

    def test_process_no_model(self, detector):
        result = detector.process(b"fake", 1, 100.0)
        assert result["frame_id"] == 1
        assert result["seatbelt"] is False
        assert result["confidence"] == 0.0

    def test_process_invalid_jpeg(self, detector, mocker):
        mock_model = mocker.MagicMock()
        detector._model = mock_model
        detector._model_loaded = True

        result = detector.process(b"invalid", 1, 100.0)
        assert result["frame_id"] == 1
        assert result["seatbelt"] is False
