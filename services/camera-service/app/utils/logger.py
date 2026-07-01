"""Structured logging utility for camera-service."""

import logging
import sys
from datetime import datetime, timezone

from app.core.config import get_settings


class CameraLogger:
    """Thread-safe structured logger with service-name prefix."""

    _instance: "CameraLogger | None" = None
    _lock: "threading.Lock | None" = None

    def __new__(cls) -> "CameraLogger":
        if cls._instance is None:
            import threading

            cls._lock = threading.Lock()
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialised = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialised:
            return
        settings = get_settings()
        self._service_name: str = settings.SERVICE_NAME
        self._logger: logging.Logger = logging.getLogger(self._service_name)
        self._logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
            formatter.converter = lambda *args: datetime.now(timezone.utc).timetuple()
            formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
            formatter.default_msec_format = "%s.%03d"
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
        self._initialised = True

    @property
    def logger(self) -> logging.Logger:
        return self._logger


def get_logger() -> logging.Logger:
    """Return the camera-service logger instance."""
    return CameraLogger().logger
