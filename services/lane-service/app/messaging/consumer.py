"""Frame consumer for Seatbelt-Service.

Consumes frames from the seatbelt.frames queue, decodes JPEG,
runs YOLO inference, and publishes results.
"""

import threading
from typing import Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, AMQPChannelError, ConnectionClosedByBroker

from app.messaging.connection import RabbitMQConnectionManager
from app.messaging.publisher import ResultPublisher
from app.services.seatbelt_detector import SeatbeltDetector
from app.utils.logger import get_logger

logger = get_logger()


class FrameConsumer:
    """Consumes JPEG frames from RabbitMQ and runs YOLO inference.

    For each consumed frame:
    1. Extracts JPEG bytes from message body
    2. Reads frame_id and timestamp from headers
    3. Runs SeatbeltDetector.process()
    4. Publishes result via ResultPublisher
    """

    EXCHANGE: str = "adas.exchange"
    EXCHANGE_TYPE: str = "topic"
    QUEUE: str = "seatbelt.frames"
    ROUTING_KEY: str = "seatbelt.frame"

    def __init__(
        self,
        connection_manager: RabbitMQConnectionManager,
        detector: SeatbeltDetector,
        publisher: ResultPublisher,
    ) -> None:
        self._connection_manager = connection_manager
        self._detector = detector
        self._publisher = publisher
        self._channel: Optional[BlockingChannel] = None
        self._consumer_tag: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._consume_loop,
            daemon=True,
            name="frame-consumer",
        )
        self._thread.start()
        logger.info("FrameConsumer thread started")

    def stop(self) -> None:
        if self._channel is not None and self._channel.is_open:
            if self._consumer_tag:
                try:
                    self._channel.basic_cancel(consumer_tag=self._consumer_tag)
                except Exception:
                    pass
            try:
                self._channel.close()
            except Exception:
                pass
        logger.info("FrameConsumer stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _consume_loop(self) -> None:
        while not self._connection_manager.stop_event.is_set():
            try:
                if not self._connection_manager.is_connected:
                    self._connection_manager.connect()

                self._channel = self._connection_manager.create_channel()
                self._channel.exchange_declare(
                    exchange=self.EXCHANGE,
                    exchange_type=self.EXCHANGE_TYPE,
                    durable=True,
                )
                self._channel.queue_declare(queue=self.QUEUE, durable=True)
                self._channel.queue_bind(
                    queue=self.QUEUE,
                    exchange=self.EXCHANGE,
                    routing_key=self.ROUTING_KEY,
                )
                self._channel.basic_qos(prefetch_count=1)

                self._consumer_tag = self._channel.basic_consume(
                    queue=self.QUEUE,
                    on_message_callback=self._on_frame_message,
                    auto_ack=True,
                )

                logger.info("FrameConsumer listening on %s", self.QUEUE)
                self._channel.start_consuming()

            except (AMQPConnectionError, AMQPChannelError, ConnectionClosedByBroker) as exc:
                logger.warning("Consumer error: %s. Reconnecting...", exc)
                self._connection_manager._connected = False
                if self._connection_manager.stop_event.wait(timeout=2.0):
                    break
            except Exception as exc:
                logger.error("Unexpected consumer error: %s", exc)
                if self._connection_manager.stop_event.wait(timeout=2.0):
                    break

    def _on_frame_message(
        self,
        channel: BlockingChannel,
        method: pika.spec.Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes,
    ) -> None:
        """Process an incoming frame message and run YOLO inference."""
        headers = properties.headers or {}
        frame_id = int(headers.get("frame_id", 0))
        timestamp = float(headers.get("timestamp", 0.0))

        logger.debug("Received frame %d", frame_id)

        result = self._detector.process(body, frame_id, timestamp)
        self._publisher.publish(result)
