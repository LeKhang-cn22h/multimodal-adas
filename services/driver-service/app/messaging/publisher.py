"""Result publisher for Driver-Service.

Publishes drowsiness inference results to RabbitMQ.
"""

import json
import threading
from typing import Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, AMQPChannelError, ConnectionClosedByBroker

from app.messaging.connection import RabbitMQConnectionManager
from app.utils.logger import get_logger

logger = get_logger()


class ResultPublisher:
    """Publishes driver inference results to RabbitMQ."""

    EXCHANGE: str = "adas.exchange"
    EXCHANGE_TYPE: str = "topic"
    ROUTING_KEY: str = "driver.result"

    def __init__(self, connection_manager: RabbitMQConnectionManager) -> None:
        self._connection_manager = connection_manager
        self._channel: Optional[BlockingChannel] = None
        self._lock: threading.Lock = threading.Lock()
        self._declared: bool = False

    def start(self) -> None:
        self._channel = self._connection_manager.create_channel()
        self._channel.exchange_declare(
            exchange=self.EXCHANGE,
            exchange_type=self.EXCHANGE_TYPE,
            durable=True,
        )
        self._declared = True
        logger.info("ResultPublisher ready (exchange=%s, routing_key=%s)", self.EXCHANGE, self.ROUTING_KEY)

    def publish(self, result: dict) -> bool:
        """Publish a drowsiness result as JSON."""
        if not self._declared or self._channel is None:
            logger.warning("ResultPublisher not started, dropping result")
            return False

        if self._channel.is_closed:
            logger.warning("Channel closed, attempting reconnect...")
            if not self._reconnect_channel():
                return False

        body = json.dumps(result).encode("utf-8")
        properties = pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json",
        )

        try:
            with self._lock:
                self._channel.basic_publish(
                    exchange=self.EXCHANGE,
                    routing_key=self.ROUTING_KEY,
                    body=body,
                    properties=properties,
                )
            return True
        except (AMQPConnectionError, AMQPChannelError, ConnectionClosedByBroker) as exc:
            logger.warning("Publish failed: %s", exc)
            if self._reconnect_channel():
                try:
                    with self._lock:
                        self._channel.basic_publish(
                            exchange=self.EXCHANGE,
                            routing_key=self.ROUTING_KEY,
                            body=body,
                            properties=properties,
                        )
                    return True
                except Exception as exc2:
                    logger.error("Retry publish failed: %s", exc2)
            return False

    def stop(self) -> None:
        if self._channel is not None and self._channel.is_open:
            try:
                self._channel.close()
                logger.info("ResultPublisher channel closed")
            except Exception as exc:
                logger.warning("Error closing publisher channel: %s", exc)
        self._declared = False

    def _reconnect_channel(self) -> bool:
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
            logger.info("ResultPublisher channel reconnected")
            return True
        except Exception as exc:
            logger.error("ResultPublisher channel reconnect failed: %s", exc)
            return False
