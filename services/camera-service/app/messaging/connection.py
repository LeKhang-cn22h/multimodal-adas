"""RabbitMQ connection manager with auto-reconnect and graceful shutdown.

Design decisions:
- Uses pika.BlockingConnection for simplicity and thread-safety per channel.
- Each consumer/publisher gets its own channel from the shared connection.
- Exponential backoff on connection failure (1s → 2s → 4s → ... → 30s cap).
- Thread-safe stop signalling via threading.Event.
"""

import threading
import time
from typing import Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from app.utils.logger import get_logger

logger = get_logger()

RECONNECT_INITIAL_DELAY: float = 1.0
RECONNECT_MAX_DELAY: float = 30.0
RECONNECT_BACKOFF: float = 2.0


class RabbitMQConnectionManager:
    """Manages a single persistent connection to RabbitMQ.

    Provides methods to create channels and handles automatic
    reconnection with exponential backoff.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        virtual_host: str = "/",
        username: str = "guest",
        password: str = "guest",
        heartbeat: int = 60,
        connection_attempts: int = 5,
        retry_delay: float = 2.0,
    ) -> None:
        self._host = host
        self._port = port
        self._virtual_host = virtual_host
        self._username = username
        self._password = password
        self._heartbeat = heartbeat
        self._connection_attempts = connection_attempts
        self._retry_delay = retry_delay

        self._connection: Optional[pika.BlockingConnection] = None
        self._lock: threading.Lock = threading.Lock()
        self._stop_event: threading.Event = threading.Event()
        self._connected: bool = False

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected and self._connection is not None and self._connection.is_open

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def connect(self) -> None:
        """Establish connection to RabbitMQ with retry."""
        credentials = pika.PlainCredentials(self._username, self._password)
        parameters = pika.ConnectionParameters(
            host=self._host,
            port=self._port,
            virtual_host=self._virtual_host,
            credentials=credentials,
            heartbeat=self._heartbeat,
            connection_attempts=self._connection_attempts,
            retry_delay=self._retry_delay,
        )

        delay = RECONNECT_INITIAL_DELAY
        while not self._stop_event.is_set():
            try:
                logger.info(
                    "Connecting to RabbitMQ at %s:%d vhost=%s",
                    self._host,
                    self._port,
                    self._virtual_host,
                )
                self._connection = pika.BlockingConnection(parameters)
                with self._lock:
                    self._connected = True
                logger.info("RabbitMQ connection established")
                return
            except (AMQPConnectionError, OSError) as exc:
                logger.warning(
                    "RabbitMQ connection failed: %s. Retrying in %.1fs...",
                    exc,
                    delay,
                )
                time.sleep(min(delay, RECONNECT_MAX_DELAY))
                delay *= RECONNECT_BACKOFF

    def create_channel(self) -> BlockingChannel:
        """Create a new channel from the managed connection.

        Raises RuntimeError if not connected.
        """
        if not self.is_connected or self._connection is None:
            raise RuntimeError("Cannot create channel: not connected to RabbitMQ")
        return self._connection.channel()

    def close(self) -> None:
        """Signal shutdown and close the connection."""
        self._stop_event.set()
        if self._connection is not None and self._connection.is_open:
            try:
                self._connection.close()
                logger.info("RabbitMQ connection closed")
            except Exception as exc:
                logger.warning("Error closing RabbitMQ connection: %s", exc)
        with self._lock:
            self._connected = False
