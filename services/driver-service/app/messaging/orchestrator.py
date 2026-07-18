"""Orchestrates camera + AI pipeline + RabbitMQ lifecycle for driver-service.
 
ADR-006 / TS-service-merge:
    CameraCaptureService (capture thread)
        → queue.Queue(maxsize=2, put_nowait)
        → worker thread (FatigueDetector + SeatbeltDetector → ResultPublisher)
 
Wires together:
    CameraCaptureService → queue.Queue → FatigueDetector
                                      → SeatbeltDetector
                                      → ResultPublisher
"""

import queue
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

from app.core.config import get_settings
from app.messaging.connection import RabbitMQConnectionManager
from app.messaging.publisher import ResultPublisher
from app.services.camera_capture_service import CameraCaptureService
from app.services.classifier_interface import IClassifier
from app.services.fatigue_detector import FatigueDetector
from app.services.feature_engineering import WindowedFeatureEngineer
from app.services.feature_service import FeatureService
from app.services.mediapipe_service import FaceLandmarkerService
from app.services.rf_classifier import RFClassifier
from app.services.rule_based_classifier import RuleBasedClassifier
from app.services.seatbelt_detector import SeatbeltDetector
from app.utils.logger import get_logger

logger = get_logger()


class MessagingOrchestrator:
    """Manages the full lifecycle: camera, AI pipeline, RabbitMQ."""

    def __init__(self) -> None:
        settings = get_settings()

        # ── Frame queue (shared: capture → worker) ──────────────────
        self._frame_queue: queue.Queue = queue.Queue(
            maxsize=settings.MAX_QUEUE_SIZE,
        )

        # ── Camera capture (background thread) ──────────────────────
        self._camera_service = CameraCaptureService(
            frame_queue=self._frame_queue,
        )

        # ── Landmark service (model wrapper) ─────────────────────────
        self._landmark_service = FaceLandmarkerService(
            model_path=settings.MODEL_PATH,
        )

        # ── Feature engineering (shared sliding-window engine) ───────
        self._feature_engineer = WindowedFeatureEngineer(
            n_stat=settings.N_STAT,
            n_perclos=settings.N_PERCLOS,
            n_vel=settings.N_VEL,
            ear_threshold=settings.EAR_THRESHOLD,
            fps=settings.FPS_ASSUMPTION,
        )
        self._feature_service = FeatureService(engine=self._feature_engineer)

        # ── Classifier (RF with rule-based fallback) ────────────────
        self._classifier: IClassifier = self._create_classifier(settings)

        # ── RabbitMQ connection ──────────────────────────────────────
        self._connection_manager = RabbitMQConnectionManager(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            username=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASS,
        )

        # ── Business services ────────────────────────────────────────
        self._detector = FatigueDetector(
            landmark_service=self._landmark_service,
            feature_service=self._feature_service,
            classifier=self._classifier,
        )
        self._publisher = ResultPublisher(self._connection_manager)

        # ── Seatbelt detector (TS-gradio-voice-alert) ────────────────
        seatbelt_model = str(
            Path(__file__).resolve().parent.parent
            / "models" / "best.pt"
        )
        self._seatbelt_detector = SeatbeltDetector(
            model_path=seatbelt_model,
            confidence_threshold=0.3,
        )

        # ── Latest result cache (for Gradio UI) ──────────────────────
        self._latest_result: Optional[dict] = None

        # ── Worker thread state ─────────────────────────────────────
        self._worker_thread: threading.Thread | None = None
        self._worker_stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def landmark_service(self) -> FaceLandmarkerService:
        return self._landmark_service

    @property
    def detector(self) -> FatigueDetector:
        return self._detector

    @property
    def camera_service(self) -> CameraCaptureService:
        """Expose camera for GET /frame and /health."""
        return self._camera_service

    @property
    def latest_result(self) -> Optional[dict]:
        """Latest combined inference result (fatigue + seatbelt).

        Returns None before the first frame has been processed.
        """
        return self._latest_result

    @property
    def seatbelt_detector(self):
        """Expose SeatbeltDetector for UI video processing."""
        return self._seatbelt_detector

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Load model, connect RabbitMQ (optional), start camera + worker."""
        logger.info("Starting driver orchestrator...")

        # 1. Load AI model
        self._landmark_service.load_model()

        # 2. Try RabbitMQ in background (do NOT block startup)
        threading.Thread(
            target=self._connect_rabbitmq,
            daemon=True,
            name="rmq-connect",
        ).start()

        # 3. Mark detector ready
        self._detector.mark_ready()

        # 4. Start worker thread (AI pipeline)
        self._worker_stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="ai-worker",
        )
        self._worker_thread.start()
        logger.info("AI worker thread started")

        # 5. Start camera capture (last — starts pushing frames)
        self._camera_service.start()

        logger.info(
            "Driver orchestrator started (classifier=%s)",
            self._classifier.method,
        )

    def stop(self) -> None:
        """Gracefully shut down all components."""
        logger.info("Stopping driver orchestrator...")

        # Stop camera first (stop pushing frames)
        self._camera_service.stop()

        # Signal worker to stop
        self._worker_stop_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

        # Stop RabbitMQ
        self._publisher.stop()
        self._connection_manager.close()

        # Release AI model
        self._landmark_service.close_model()

        logger.info("Driver orchestrator stopped")

    # ------------------------------------------------------------------
    # Worker thread (camera → queue → AI → RabbitMQ)
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Worker thread: read frames from queue, run AI, publish results.

        No drop logic on worker side — queue maxsize is enforced by
        capture thread via put_nowait, so queue size is always
        ≤ MAX_QUEUE_SIZE.  Worker simply processes whatever arrives.

        TS-gradio-voice-alert: added SeatbeltDetector + latest_result cache.
        """
        frame_id = 0
        while not self._worker_stop_event.is_set():
            try:
                jpeg_bytes = self._frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            timestamp = time.time()

            # ── Fatigue detection ──────────────────────────────────
            fatigue_result = self._detector.process(
                jpeg_bytes, frame_id, timestamp,
            )

            # ── Seatbelt detection (decode JPEG for YOLO) ──────────
            try:
                import cv2
                np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    sb = self._seatbelt_detector.detect(frame)
                else:
                    sb = {"has_seatbelt": False, "seatbelt_confidence": None}
            except Exception:
                sb = {"has_seatbelt": False, "seatbelt_confidence": None}

            # ── Combine & cache ────────────────────────────────────
            combined = {
                **fatigue_result,
                "has_seatbelt": sb["has_seatbelt"],
                "seatbelt_confidence": sb.get("seatbelt_confidence"),
            }
            self._latest_result = combined

            # ── Publish ────────────────────────────────────────────
            self._publisher.publish(combined)
            frame_id += 1

    # ------------------------------------------------------------------
    # RabbitMQ background connection
    # ------------------------------------------------------------------

    def _connect_rabbitmq(self) -> None:
        """Connect to RabbitMQ in background (non-blocking startup)."""
        try:
            self._connection_manager.connect_or_fail(max_retries=1)
            self._publisher.start()
            logger.info("RabbitMQ connected, ResultPublisher ready")
        except Exception as exc:
            logger.warning(
                "RabbitMQ unavailable (%s). Running without publish.", exc,
            )

    # ------------------------------------------------------------------
    # Classifier factory (TS-rf-integration)
    # ------------------------------------------------------------------

    @staticmethod
    def _create_classifier(settings) -> IClassifier:
        """Try loading RF model; fall back to rule-based on failure."""
        model_path = settings.RF_MODEL_PATH

        if not settings.RF_FALLBACK_ENABLED:
            logger.info("RF fallback disabled — loading model from %s", model_path)
            return RFClassifier(model_path)

        try:
            if not Path(model_path).exists():
                raise FileNotFoundError(
                    f"Model file not found: {model_path}"
                )
            classifier: IClassifier = RFClassifier(model_path)
            logger.info("Loaded RF model from %s", model_path)
            return classifier
        except Exception as exc:
            logger.warning(
                "Cannot load RF model: %s. Falling back to rule-based.", exc,
            )
            return RuleBasedClassifier()


_orchestrator: MessagingOrchestrator | None = None


def get_orchestrator() -> MessagingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MessagingOrchestrator()
    return _orchestrator
