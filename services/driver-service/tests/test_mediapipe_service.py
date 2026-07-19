"""Unit tests for FaceLandmarkerService + FaceLandmarkerResult.

Tests the MediaPipe wrapper created in TS-landmark-refactor.
All tests use mock MediaPipe — no model file or webcam required.
"""

import numpy as np
import pytest


# =============================================================================
#  FaceLandmarkerResult
# =============================================================================


class TestFaceLandmarkerResult:
    """Tests for the FaceLandmarkerResult dataclass."""

    def test_create_no_face(self):
        """FaceLandmarkerResult with face_detected=False should have None fields."""
        from app.services.mediapipe_service import FaceLandmarkerResult

        result = FaceLandmarkerResult(
            face_detected=False,
            landmarks=None,
            transformation_matrix=None,
        )
        assert result.face_detected is False
        assert result.landmarks is None
        assert result.transformation_matrix is None

    def test_create_with_face(self):
        """FaceLandmarkerResult with face_detected=True should hold data."""
        from app.services.mediapipe_service import FaceLandmarkerResult

        matrix = np.eye(4, dtype=np.float64)
        result = FaceLandmarkerResult(
            face_detected=True,
            landmarks=[1, 2, 3],  # simplified for test
            transformation_matrix=matrix,
        )
        assert result.face_detected is True
        assert result.landmarks == [1, 2, 3]
        assert np.array_equal(result.transformation_matrix, matrix)

    def test_fields_are_accessible(self):
        """All three fields should be accessible as attributes."""
        from app.services.mediapipe_service import FaceLandmarkerResult

        result = FaceLandmarkerResult(
            face_detected=True,
            landmarks=[],
            transformation_matrix=np.zeros((4, 4)),
        )
        assert hasattr(result, "face_detected")
        assert hasattr(result, "landmarks")
        assert hasattr(result, "transformation_matrix")


# =============================================================================
#  FaceLandmarkerService
# =============================================================================


class TestFaceLandmarkerService:
    """Tests for the FaceLandmarkerService wrapper."""

    # ── Constructor & properties ──────────────────────────────────────

    def test_constructor_stores_model_path(self):
        """Constructor should store model_path but NOT load the model yet."""
        from app.services.mediapipe_service import FaceLandmarkerService

        svc = FaceLandmarkerService(model_path="test.task")
        assert svc._model_path == "test.task"
        assert svc.is_loaded is False  # not loaded yet

    def test_is_loaded_after_load_model(self, mocker):
        """is_loaded should be True after load_model() succeeds."""
        from app.services.mediapipe_service import FaceLandmarkerService

        # Mock the entire FaceLandmarker class before importing the module
        mock_face_landmarker_cls = mocker.patch(
            "app.services.mediapipe_service.FaceLandmarker"
        )
        mock_landmarker = mocker.MagicMock()
        mock_face_landmarker_cls.create_from_options.return_value = mock_landmarker

        svc = FaceLandmarkerService(model_path="test.task")
        assert svc.is_loaded is False

        svc.load_model()
        assert svc.is_loaded is True

    def test_close_model_sets_not_loaded(self, mocker):
        """is_loaded should be False after close_model()."""
        from app.services.mediapipe_service import FaceLandmarkerService

        mock_face_landmarker_cls = mocker.patch(
            "app.services.mediapipe_service.FaceLandmarker"
        )
        mock_landmarker = mocker.MagicMock()
        mock_face_landmarker_cls.create_from_options.return_value = mock_landmarker

        svc = FaceLandmarkerService(model_path="test.task")
        svc.load_model()
        assert svc.is_loaded is True

        svc.close_model()
        assert svc.is_loaded is False
        mock_landmarker.close.assert_called_once()

    # ── detect() ─────────────────────────────────────────────────────

    def test_detect_before_load_raises(self):
        """detect() should raise RuntimeError if model not loaded."""
        from app.services.mediapipe_service import FaceLandmarkerService

        svc = FaceLandmarkerService(model_path="test.task")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with pytest.raises(RuntimeError, match="load_model"):
            svc.detect(frame, 0)

    def test_detect_no_face(self, mocker):
        """detect() should return face_detected=False when no face found."""
        from app.services.mediapipe_service import FaceLandmarkerService

        mock_cls = mocker.patch("app.services.mediapipe_service.FaceLandmarker")
        mock_landmarker = mocker.MagicMock()
        mock_cls.create_from_options.return_value = mock_landmarker

        # Simulate MediaPipe returning no face_landmarks
        mock_result = mocker.MagicMock()
        mock_result.face_landmarks = []  # empty → no face
        mock_landmarker.detect_for_video.return_value = mock_result

        svc = FaceLandmarkerService(model_path="test.task")
        svc.load_model()

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = svc.detect(frame, 0)

        assert result.face_detected is False
        assert result.landmarks is None
        assert result.transformation_matrix is None

    def test_detect_with_face_returns_landmarks(self, mocker):
        """detect() should extract landmarks when face is found."""
        from app.services.mediapipe_service import FaceLandmarkerService

        mock_cls = mocker.patch("app.services.mediapipe_service.FaceLandmarker")
        mock_landmarker = mocker.MagicMock()
        mock_cls.create_from_options.return_value = mock_landmarker

        # Simulate MediaPipe returning one face with landmarks
        fake_landmarks = [mocker.MagicMock() for _ in range(478)]
        fake_matrix = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]

        mock_result = mocker.MagicMock()
        mock_result.face_landmarks = [fake_landmarks]
        mock_result.facial_transformation_matrixes = [fake_matrix]
        mock_landmarker.detect_for_video.return_value = mock_result

        svc = FaceLandmarkerService(model_path="test.task")
        svc.load_model()

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = svc.detect(frame, 1000)

        assert result.face_detected is True
        assert result.landmarks is fake_landmarks
        assert result.transformation_matrix is not None
        assert result.transformation_matrix.shape == (4, 4)

    def test_detect_no_matrix_fallback(self, mocker):
        """detect() should set transformation_matrix=None when MediaPipe
        does not return facial_transformation_matrixes."""
        from app.services.mediapipe_service import FaceLandmarkerService

        mock_cls = mocker.patch("app.services.mediapipe_service.FaceLandmarker")
        mock_landmarker = mocker.MagicMock()
        mock_cls.create_from_options.return_value = mock_landmarker

        fake_landmarks = [mocker.MagicMock() for _ in range(478)]

        mock_result = mocker.MagicMock()
        mock_result.face_landmarks = [fake_landmarks]
        mock_result.facial_transformation_matrixes = []  # empty!

        mock_landmarker.detect_for_video.return_value = mock_result

        svc = FaceLandmarkerService(model_path="test.task")
        svc.load_model()

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = svc.detect(frame, 0)

        assert result.face_detected is True
        assert result.transformation_matrix is None  # safe fallback

    def test_load_model_is_idempotent(self, mocker):
        """load_model() called twice should not create a second instance."""
        from app.services.mediapipe_service import FaceLandmarkerService

        mock_cls = mocker.patch("app.services.mediapipe_service.FaceLandmarker")
        mock_landmarker = mocker.MagicMock()
        mock_cls.create_from_options.return_value = mock_landmarker

        svc = FaceLandmarkerService(model_path="test.task")
        svc.load_model()
        svc.load_model()  # second call

        # create_from_options should only be called once
        assert mock_cls.create_from_options.call_count == 1
