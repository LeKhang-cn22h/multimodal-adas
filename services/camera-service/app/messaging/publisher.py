"""Frame publisher for RabbitMQ.

Publishes JPEG frame bytes to the configured exchange with routing key.
Uses AMQP headers for metadata (frame_id, timestamp) to keep the body as raw JPEG.
"""

import json
import threading
from typing import Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, AMQPChannelError, ConnectionClosedByBroker

from app.messaging.connection import RabbitMQConnectionManager
from app.models.messages import FrameMessage
from app.utils.logger import get_logger

logger = get_logger()


class FramePublisher:
    """Publishes JPEG frame bytes to RabbitMQ exchange.

    Each call to publish() sends one message with raw JPEG body
    and metadata in AMQP headers.
    """

    EXCHANGE: str = "adas.exchange"
    EXCHANGE_TYPE: str = "topic"

    def __init__(self, connection_manager: RabbitMQConnectionManager, routing_key: str) -> None:
        self._connection_manager = connection_manager
        self._routing_key = routing_key
        self._channel: Optional[BlockingChannel] = None
        self._lock: threading.Lock = threading.Lock()
        self._declared: bool = False

    def start(self) -> None:
        """Create channel and declare exchange."""
        self._channel = self._connection_manager.create_channel()
        self._channel.exchange_declare(
            exchange=self.EXCHANGE,
            exchange_type=self.EXCHANGE_TYPE,
            durable=True,
        )
        self._declared = True
        logger.info(
            "FramePublisher ready (exchange=%s, routing_key=%s)",
            self.EXCHANGE,
            self._routing_key,
        )

    def publish(self, jpeg_bytes: bytes, metadata: FrameMessage) -> bool:
        """Publish a single JPEG frame to RabbitMQ.

        Returns True on success, False on failure (caller decides retry).
        """
        if not self._declared or self._channel is None:
            logger.warning("FramePublisher not started, dropping frame %d", metadata.frame_id)
            return False

        if self._channel.is_closed:
            logger.warning("Channel closed, attempting reconnect...")
            if not self._reconnect_channel():
                return False

        properties = pika.BasicProperties(
            delivery_mode=2,
            content_type="image/jpeg",
            headers={
                "frame_id": metadata.frame_id,
                "timestamp": str(metadata.timestamp),
            },
        )

        try:
            with self._lock:
                self._channel.basic_publish(
                    exchange=self.EXCHANGE,
                    routing_key=self._routing_key,
                    body=jpeg_bytes,
                    properties=properties,
                )
            return True
        except (AMQPConnectionError, AMQPChannelError, ConnectionClosedByBroker) as exc:
            logger.warning("Publish failed for frame %d: %s", metadata.frame_id, exc)
            if self._reconnect_channel():
                try:
                    with self._lock:
                        self._channel.basic_publish(
                            exchange=self.EXCHANGE,
                            routing_key=self._routing_key,
                            body=jpeg_bytes,
                            properties=properties,
                        )
                    return True
                except Exception as exc2:
                    logger.error("Retry publish failed for frame %d: %s", metadata.frame_id, exc2)
            return False

    def stop(self) -> None:
        """Close the publisher channel."""
        if self._channel is not None and self._channel.is_open:
            try:
                self._channel.close()
                logger.info("FramePublisher channel closed")
            except Exception as exc:
                logger.warning("Error closing publisher channel: %s", exc)
        self._declared = False

    def _reconnect_channel(self) -> bool:
        """Attempt to recreate the channel after connection loss."""
        try:
            if not self._connection_manager.is_connected:
                self._connection_manager.connect()
            self._channel = self._connection_manager.create_channel()
            self._channel.exchange_declare(
                exchange=self.EXCHANGE,
                exchange_type=self.EXCHANGE_TYPE,
                durable=True,
            )
            self._declared = True
            logger.info("FramePublisher channel reconnected")
            return True
        except Exception as exc:
            logger.error("FramePublisher channel reconnect failed: %s", exc)
            return False
