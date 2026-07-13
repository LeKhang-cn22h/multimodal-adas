"""Application configuration for seatbelt-service."""

import os
from functools import lru_cache


class Settings:
    """Seatbelt service settings loaded from environment variables."""

    CAMERA_SERVICE_URL: str = os.getenv("CAMERA_SERVICE_URL", "http://camera-service:8005")
    MODEL_PATH: str = os.getenv("MODEL_PATH", "best.pt")
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.3"))
    WARNING_FRAMES: int = int(os.getenv("WARNING_FRAMES", "10"))
    POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "3.0"))
    PORT: int = int(os.getenv("PORT", "8007"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SERVICE_NAME: str = "seatbelt-service"

    AGGREGATOR_URL: str = os.getenv("AGGREGATOR_URL", "http://aggregator-service:8003/event")


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
