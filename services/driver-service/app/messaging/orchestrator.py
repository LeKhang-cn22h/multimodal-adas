"""Orchestrates RabbitMQ lifecycle for driver-service.

Wires together: FrameConsumer → FatigueDetector → ResultPublisher.
"""

from app.core.config import get_settings
from app.messaging.connection import RabbitMQConnectionManager
from app.messaging.consumer import FrameConsumer
from app.messaging.publisher import ResultPublisher
from app.services.fatigue_detector import FatigueDetector
from app.utils.logger import get_logger

logger = get_logger()


class MessagingOrchestrator:
    """Manages the full RabbitMQ lifecycle for driver-service."""

    def __init__(self) -> None:
        settings = get_settings()

        self._connection_manager = RabbitMQConnectionManager(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            username=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASS,
        )

        self._detector = FatigueDetector()
        self._publisher = ResultPublisher(self._connection_manager)
        self._consumer = FrameConsumer(
            self._connection_manager,
            self._detector,
            self._publisher,
        )

    @property
    def detector(self) -> FatigueDetector:
        return self._detector

    def start(self) -> None:
        logger.info("Starting driver messaging orchestrator...")

        self._detector.load_model()

        self._connection_manager.connect()

        self._publisher.start()
        self._consumer.start()

        logger.info("Driver messaging orchestrator started")

    def stop(self) -> None:
        logger.info("Stopping driver messaging orchestrator...")
        self._consumer.stop()
        self._publisher.stop()
        self._connection_manager.close()
        self._detector.close_model()
        logger.info("Driver messaging orchestrator stopped")


_orchestrator: MessagingOrchestrator | None = None


def get_orchestrator() -> MessagingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MessagingOrchestrator()
    return _orchestrator
