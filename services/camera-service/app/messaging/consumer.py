"""Result consumer for RabbitMQ.

Consumes driver.results and seatbelt.results from RabbitMQ
and stores the latest result for overlay display.
"""

import json
import threading
from typing import Callable, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, AMQPChannelError, ConnectionClosedByBroker

from app.messaging.connection import RabbitMQConnectionManager
from app.models.messages import DriverResultMessage, SeatbeltResultMessage
from app.utils.logger import get_logger

logger = get_logger()


class ResultConsumer:
    """Consumes AI inference results from RabbitMQ queues.

    Runs a background thread that blocks on basic_consume and
    invokes provided callbacks for each received message.
    """

    EXCHANGE: str = "adas.exchange"
    EXCHANGE_TYPE: str = "topic"

    def __init__(self, connection_manager: RabbitMQConnectionManager) -> None:
        self._connection_manager = connection_manager
        self._channel: Optional[BlockingChannel] = None
        self._consumer_tags: list[str] = []
        self._thread: Optional[threading.Thread] = None
        self._driver_callback: Optional[Callable[[DriverResultMessage], None]] = None
        self._seatbelt_callback: Optional[Callable[[SeatbeltResultMessage], None]] = None

        self._latest_driver_result: Optional[DriverResultMessage] = None
        self._latest_seatbelt_result: Optional[SeatbeltResultMessage] = None
        self._result_lock: threading.Lock = threading.Lock()

    @property
    def latest_driver_result(self) -> Optional[DriverResultMessage]:
        with self._result_lock:
            return self._latest_driver_result

    @property
    def latest_seatbelt_result(self) -> Optional[SeatbeltResultMessage]:
        with self._result_lock:
            return self._latest_seatbelt_result

    def on_driver_result(self, callback: Callable[[DriverResultMessage], None]) -> None:
        self._driver_callback = callback

    def on_seatbelt_result(self, callback: Callable[[SeatbeltResultMessage], None]) -> None:
        self._seatbelt_callback = callback

    def start(self) -> None:
        """Declare exchange, bind queues, and start consuming in background thread."""
        self._thread = threading.Thread(
            target=self._consume_loop,
            daemon=True,
            name="result-consumer",
        )
        self._thread.start()
        logger.info("ResultConsumer thread started")

    def stop(self) -> None:
        """Signal the consumer thread to stop and clean up."""
        if self._channel is not None and self._channel.is_open:
            for tag in self._consumer_tags:
                try:
                    self._channel.basic_cancel(consumer_tag=tag)
                except Exception:
                    pass
            try:
                self._channel.close()
            except Exception:
                pass
        logger.info("ResultConsumer stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _consume_loop(self) -> None:
        """Main consumer loop with reconnect logic."""
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

                self._setup_queue("driver.results", "driver.result", self._on_driver_message)
                self._setup_queue("seatbelt.results", "seatbelt.result", self._on_seatbelt_message)

                logger.info("ResultConsumer listening on driver.results + seatbelt.results")
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

    def _setup_queue(
        self,
        queue_name: str,
        routing_key: str,
        callback: Callable,
    ) -> None:
        """Declare a queue, bind it, and register a consumer."""
        if self._channel is None:
            return
        self._channel.queue_declare(queue=queue_name, durable=True)
        self._channel.queue_bind(
            queue=queue_name,
            exchange=self.EXCHANGE,
            routing_key=routing_key,
        )
        tag = self._channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True,
        )
        self._consumer_tags.append(tag)

    def _on_driver_message(
        self,
        channel: BlockingChannel,
        method: pika.spec.Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes,
    ) -> None:
        """Handle incoming driver result message."""
        try:
            data = json.loads(body.decode("utf-8"))
            result = DriverResultMessage(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse driver result: %s", exc)
            return

        with self._result_lock:
            self._latest_driver_result = result

        if self._driver_callback:
            try:
                self._driver_callback(result)
            except Exception as exc:
                logger.warning("Driver callback error: %s", exc)

    def _on_seatbelt_message(
        self,
        channel: BlockingChannel,
        method: pika.spec.Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes,
    ) -> None:
        """Handle incoming seatbelt result message."""
        try:
            data = json.loads(body.decode("utf-8"))
            result = SeatbeltResultMessage(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse seatbelt result: %s", exc)
            return

        with self._result_lock:
            self._latest_seatbelt_result = result

        if self._seatbelt_callback:
            try:
                self._seatbelt_callback(result)
            except Exception as exc:
                logger.warning("Seatbelt callback error: %s", exc)
