"""Application configuration for driver-service."""

import os
from functools import lru_cache


class Settings:
    """Driver service settings loaded from environment variables."""

    PORT: int = int(os.getenv("PORT", "8001"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SERVICE_NAME: str = "driver-service"

    EAR_THRESHOLD: float = float(os.getenv("EAR_THRESHOLD", "0.22"))
    DROWSY_FRAMES: int = int(os.getenv("DROWSY_FRAMES", "60"))
    SLIDING_WINDOW_SIZE: int = int(os.getenv("SLIDING_WINDOW_SIZE", "90"))

    MODEL_PATH: str = os.getenv("MODEL_PATH", "face_landmarker.task")

    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_VHOST: str = os.getenv("RABBITMQ_VHOST", "/")
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS: str = os.getenv("RABBITMQ_PASS", "guest")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
