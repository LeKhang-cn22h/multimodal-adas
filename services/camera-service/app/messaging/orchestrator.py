"""Orchestrates RabbitMQ lifecycle for camera-service.

Wires together: CameraManager → FramePublishers → RabbitMQ
                ResultConsumer → DisplayOverlay → cv2.imshow
"""

import threading
import time

from app.core.config import get_settings
from app.messaging.connection import RabbitMQConnectionManager
from app.messaging.consumer import ResultConsumer
from app.messaging.publisher import FramePublisher
from app.models.messages import FrameMessage
from app.services.camera_manager import CameraManager
from app.services.camera_manager_instance import camera_manager
from app.services.display import DisplayOverlay
from app.utils.logger import get_logger

logger = get_logger()


class MessagingOrchestrator:
    """Manages the full lifecycle of RabbitMQ messaging for camera-service.

    Responsibilities:
    - Connect to RabbitMQ
    - Create FramePublishers (driver + seatbelt)
    - Wire CameraManager frame callback
    - Create ResultConsumer
    - Create DisplayOverlay
    - Graceful shutdown
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings

        # Connection A: dedicated to publishers. All publish() calls happen
        # synchronously on the camera capture thread, so sharing this single
        # connection between the two publishers is safe.
        self._connection_manager = RabbitMQConnectionManager(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            username=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASS,
        )

        # Connection B: dedicated to the consumer. ResultConsumer runs
        # channel.start_consuming() (a blocking call) on its own thread, so
        # it MUST NOT share a pika.BlockingConnection with the publishers —
        # pika connections are not safe to use concurrently from multiple
        # threads even across different channels. Sharing one caused
        # AMQP frame corruption (UNEXPECTED_FRAME / class 60 errors).
        self._consumer_connection_manager = RabbitMQConnectionManager(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            username=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASS,
        )

        self._driver_publisher = FramePublisher(
            self._connection_manager,
            routing_key="driver.frame",
        )
        self._seatbelt_publisher = FramePublisher(
            self._connection_manager,
            routing_key="seatbelt.frame",
        )
        self._consumer = ResultConsumer(self._consumer_connection_manager)
        self._display = DisplayOverlay(camera_manager)

        self._last_seatbelt_frame_time: float = 0.0
        self._seatbelt_interval: float = settings.SEATBELT_FRAME_INTERVAL

    def start(self) -> None:
        """Connect to RabbitMQ and start all consumers/publishers."""
        logger.info("Starting messaging orchestrator...")

        self._connection_manager.connect()
        # Consumer gets its own physical connection, established here so
        # it's ready before ResultConsumer's thread starts consuming.
        self._consumer_connection_manager.connect()

        self._driver_publisher.start()
        self._seatbelt_publisher.start()

        logger.info("Publishers ready. Wiring frame callback...")
        camera_manager.set_on_frame_callback(self._on_frame_captured)

        self._consumer.on_driver_result(self._display.update_driver_result)
        self._consumer.on_seatbelt_result(self._display.update_seatbelt_result)
        self._consumer.start()

        self._display.start()

        logger.info("Messaging orchestrator started")

    def stop(self) -> None:
        """Gracefully shut down all messaging components."""
        logger.info("Stopping messaging orchestrator...")
        camera_manager.set_on_frame_callback(None)
        self._display.stop()
        self._consumer.stop()
        self._driver_publisher.stop()
        self._seatbelt_publisher.stop()
        self._connection_manager.close()
        self._consumer_connection_manager.close()
        logger.info("Messaging orchestrator stopped")

    # ------------------------------------------------------------------
    # Frame callback
    # ------------------------------------------------------------------

    def _on_frame_captured(self, jpeg_bytes: bytes, frame_id: int, timestamp: float) -> None:
        """Called by CameraManager on every captured frame.

        Publishes every frame to driver queue, and throttled frames
        to seatbelt queue based on configured interval.
        """
        metadata = FrameMessage(frame_id=frame_id, timestamp=timestamp)

        self._driver_publisher.publish(jpeg_bytes, metadata)

        now = time.time()
        if now - self._last_seatbelt_frame_time >= self._seatbelt_interval:
            self._seatbelt_publisher.publish(jpeg_bytes, metadata)
            self._last_seatbelt_frame_time = now


_messaging_orchestrator: MessagingOrchestrator | None = None


def get_orchestrator() -> MessagingOrchestrator:
    global _messaging_orchestrator
    if _messaging_orchestrator is None:
        _messaging_orchestrator = MessagingOrchestrator()
    return _messaging_orchestrator