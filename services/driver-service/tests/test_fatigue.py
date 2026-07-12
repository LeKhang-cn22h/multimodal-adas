"""Unit tests for FatigueDetector (TS-fatigue-classifier — 3-arg constructor)."""

import numpy as np
import pytest


class MockLandmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y


# =============================================================================
#  EAR pure function tests (unchanged)
# =============================================================================


class TestCalculateEAR:
    def _make_landmarks(self, points):
        return [MockLandmark(x, y) for x, y in points]

    def test_normal_eye(self):
        from app.utils.ear import calculate_ear

        landmarks = self._make_landmarks([
            (0.35, 0.50), (0.37, 0.48), (0.39, 0.46),
            (0.60, 0.50), (0.39, 0.54), (0.37, 0.52),
        ])
        ear = calculate_ear(landmarks, [0, 1, 2, 3, 4, 5])
        assert 0.20 < ear < 0.40

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


# =============================================================================
#  Helpers: create mock services for FatigueDetector tests
# =============================================================================


def _make_mock_landmark_service(mocker, is_loaded=True):
    """Return a MagicMock that satisfies the FaceLandmarkerService interface."""
    mock_svc = mocker.MagicMock()
    mock_svc.is_loaded = is_loaded
    return mock_svc


def _make_mock_feature_service(mocker, ear_avg=0.25):
    """Return a MagicMock that satisfies the FeatureService interface."""
    from app.services.feature_service import FeatureVector

    mock_feat = mocker.MagicMock()
    fv = FeatureVector(
        ear_left=ear_avg, ear_right=ear_avg, ear_avg=ear_avg,
    )
    mock_feat.extract.return_value = fv
    return mock_feat


def _make_mock_classifier(mocker):
    """Return a MagicMock that satisfies the IClassifier interface."""
    from app.schemas.classification_result import ClassificationResult

    mock_clf = mocker.MagicMock()
    mock_clf.method = "mock"
    mock_clf.classify.return_value = ClassificationResult(
        fatigue_score=50,
        fatigue_level="Tired",
        confidence=0.8,
        classification_method="mock",
        features={"ear": 0.2, "perclos": 20.0, "mar": 0.1,
                   "yaw": 0.0, "pitch": 0.0, "roll": 0.0},
    )
    return mock_clf


# =============================================================================
#  FatigueDetector tests (TS-fatigue-classifier: 3-arg constructor)
# =============================================================================


class TestFatigueDetector:
    """Tests for FatigueDetector with IClassifier injection."""

    def test_constructor_accepts_all_services(self, mocker):
        """FatigueDetector should accept all 3 injected services."""
        from app.services.fatigue_detector import FatigueDetector

        mock_svc = _make_mock_landmark_service(mocker)
        mock_feat = _make_mock_feature_service(mocker)
        mock_clf = _make_mock_classifier(mocker)

        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock()

        detector = FatigueDetector(
            landmark_service=mock_svc,
            feature_service=mock_feat,
            classifier=mock_clf,
        )
        assert detector.is_loaded is True
        assert detector.classification_method == "mock"

    def test_is_loaded_delegates_to_service(self, mocker):
        """is_loaded should delegate to the injected landmark service."""
        from app.services.fatigue_detector import FatigueDetector

        mock_svc = _make_mock_landmark_service(mocker, is_loaded=False)
        mock_svc.is_loaded = False
        mock_feat = _make_mock_feature_service(mocker)
        mock_clf = _make_mock_classifier(mocker)

        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock()

        detector = FatigueDetector(
            landmark_service=mock_svc,
            feature_service=mock_feat,
            classifier=mock_clf,
        )
        assert detector.is_loaded is False

    def test_decode_jpeg(self, mocker):
        """_decode_jpeg (static method) should decode valid JPEG bytes."""
        from app.services.fatigue_detector import FatigueDetector

        import cv2
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", img)
        jpeg_data = jpeg_bytes.tobytes()

        result = FatigueDetector._decode_jpeg(jpeg_data)
        assert result is not None
        assert result.shape == (100, 100, 3)

    def test_decode_jpeg_invalid(self, mocker):
        """_decode_jpeg should return None for invalid bytes."""
        from app.services.fatigue_detector import FatigueDetector

        result = FatigueDetector._decode_jpeg(b"not a valid jpeg")
        assert result is None

    def test_build_result_new_schema(self, mocker):
        """_build_result should return dict matching driver.result schema."""
        from app.services.fatigue_detector import FatigueDetector

        mock_svc = _make_mock_landmark_service(mocker)
        mock_feat = _make_mock_feature_service(mocker)
        mock_clf = _make_mock_classifier(mocker)
        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock()

        detector = FatigueDetector(
            landmark_service=mock_svc,
            feature_service=mock_feat,
            classifier=mock_clf,
        )
        result = detector._build_result(
            frame_id=42,
            timestamp=100.0,
            fatigue_score=72,
            fatigue_level="Drowsy",
            confidence=0.92,
            classification_method="rule_based",
        )
        assert result["frame_id"] == 42
        assert result["fatigue_score"] == 72
        assert result["fatigue_level"] == "Drowsy"
        assert result["confidence"] == 0.92
        assert result["classification_method"] == "rule_based"
        assert "features" in result
        # Verify old keys NOT present
        assert "sleepy" not in result

    def test_stats_defaults(self, mocker):
        """get_stats should return new schema keys when no frames processed."""
        from app.services.fatigue_detector import FatigueDetector

        mock_svc = _make_mock_landmark_service(mocker)
        mock_feat = _make_mock_feature_service(mocker)
        mock_clf = _make_mock_classifier(mocker)
        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock()

        detector = FatigueDetector(
            landmark_service=mock_svc,
            feature_service=mock_feat,
            classifier=mock_clf,
        )
        stats = detector.get_stats()
        assert "uptime" in stats
        assert "total_frames" in stats
        assert "classification_method" in stats
        assert "fatigue_level_distribution" in stats
        assert stats["total_frames"] == 0
        # Old keys should not exist
        assert "drowsy_events" not in stats

    def test_process_decode_failure(self, mocker):
        """process() should return Unknown result for invalid JPEG."""
        from app.services.fatigue_detector import FatigueDetector

        mock_svc = _make_mock_landmark_service(mocker)
        mock_feat = _make_mock_feature_service(mocker)
        mock_clf = _make_mock_classifier(mocker)
        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock()

        detector = FatigueDetector(
            landmark_service=mock_svc,
            feature_service=mock_feat,
            classifier=mock_clf,
        )
        result = detector.process(b"bad bytes", 1, 100.0)
        assert result["frame_id"] == 1
        assert result["fatigue_score"] == -1
        assert result["fatigue_level"] == "Unknown"
        assert result["confidence"] == 0.0

    def test_process_no_face_detected(self, mocker):
        """process() should return Unknown when no face is detected."""
        from app.services.fatigue_detector import FatigueDetector
        from app.services.mediapipe_service import FaceLandmarkerResult

        mock_svc = _make_mock_landmark_service(mocker)
        mock_svc.detect.return_value = FaceLandmarkerResult(
            face_detected=False,
            landmarks=None,
            transformation_matrix=None,
        )
        mock_feat = _make_mock_feature_service(mocker)
        mock_clf = _make_mock_classifier(mocker)

        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock()

        import cv2
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", img)

        detector = FatigueDetector(
            landmark_service=mock_svc,
            feature_service=mock_feat,
            classifier=mock_clf,
        )
        result = detector.process(jpeg_bytes.tobytes(), 1, 100.0)
        assert result["fatigue_score"] == -1
        assert result["fatigue_level"] == "Unknown"
        assert result["confidence"] == 0.0

    def test_mark_ready_sets_start_time(self, mocker):
        """mark_ready() should allow get_stats() to report uptime."""
        from app.services.fatigue_detector import FatigueDetector

        mock_svc = _make_mock_landmark_service(mocker)
        mock_feat = _make_mock_feature_service(mocker)
        mock_clf = _make_mock_classifier(mocker)
        mock_settings = mocker.patch("app.services.fatigue_detector.get_settings")
        mock_settings.return_value = mocker.MagicMock()

        detector = FatigueDetector(
            landmark_service=mock_svc,
            feature_service=mock_feat,
            classifier=mock_clf,
        )
        detector.mark_ready()
        stats = detector.get_stats()
        assert stats["uptime"] >= 0.0
