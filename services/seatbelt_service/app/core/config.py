"""Application configuration for seatbelt-service."""

import os
from functools import lru_cache


class Settings:
    """Seatbelt service settings loaded from environment variables."""

    MODEL_PATH: str = os.getenv("MODEL_PATH", "best.pt")
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.3"))
    WARNING_FRAMES: int = int(os.getenv("WARNING_FRAMES", "10"))
    POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "3.0"))
    PORT: int = int(os.getenv("PORT", "8007"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SERVICE_NAME: str = "seatbelt-service"

    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_VHOST: str = os.getenv("RABBITMQ_VHOST", "/")
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS: str = os.getenv("RABBITMQ_PASS", "guest")

    AGGREGATOR_URL: str = os.getenv("AGGREGATOR_URL", "http://aggregator-service:8003/event")


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
