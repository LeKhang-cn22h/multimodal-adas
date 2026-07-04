"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache


class Settings:
    """Camera service settings.

    All values can be overridden via environment variables.
    """

    CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))
    JPEG_QUALITY: int = int(os.getenv("JPEG_QUALITY", "85"))
    FRAME_WIDTH: int = int(os.getenv("FRAME_WIDTH", "640"))
    FRAME_HEIGHT: int = int(os.getenv("FRAME_HEIGHT", "480"))
    DEFAULT_FPS: int = int(os.getenv("DEFAULT_FPS", "30"))
    PORT: int = int(os.getenv("PORT", "8005"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SERVICE_NAME: str = "camera-service"

    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_VHOST: str = os.getenv("RABBITMQ_VHOST", "/")
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS: str = os.getenv("RABBITMQ_PASS", "guest")

    SEATBELT_FRAME_INTERVAL: float = float(os.getenv("SEATBELT_FRAME_INTERVAL", "600.0"))


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
