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

    # ── Feature extraction thresholds (TS-feature-extraction) ──────────
    MAR_THRESHOLD: float = float(os.getenv("MAR_THRESHOLD", "0.6"))
    PERCLOS_WINDOW_SECONDS: int = int(os.getenv("PERCLOS_WINDOW_SECONDS", "30"))
    HEAD_POSE_PITCH_THRESHOLD: float = float(os.getenv("HEAD_POSE_PITCH_THRESHOLD", "20.0"))
    HEAD_POSE_YAW_THRESHOLD: float = float(os.getenv("HEAD_POSE_YAW_THRESHOLD", "25.0"))
    FPS_ASSUMPTION: int = int(os.getenv("FPS_ASSUMPTION", "30"))

    # ── Window sizes (frames) — đồng bộ với TS-dataset-training.md ────
    N_STAT: int = int(os.getenv("N_STAT", "300"))          # 10 s @ 30 fps → 28 stats
    N_PERCLOS: int = int(os.getenv("N_PERCLOS", "900"))    # 30 s @ 30 fps → PERCLOS + blink
    N_VEL: int = int(os.getenv("N_VEL", "30"))             #  1 s @ 30 fps → 3 velocities

    # ── Rule-based classifier thresholds (TS-fatigue-classifier) ───────
    PERCLOS_AWAKE_MAX: float = float(os.getenv("PERCLOS_AWAKE_MAX", "15.0"))
    PERCLOS_TIRED_MAX: float = float(os.getenv("PERCLOS_TIRED_MAX", "25.0"))
    PERCLOS_DROWSY_MAX: float = float(os.getenv("PERCLOS_DROWSY_MAX", "40.0"))
    YAWN_COUNT_THRESHOLD: int = int(os.getenv("YAWN_COUNT_THRESHOLD", "3"))
    YAWN_WINDOW_SECONDS: int = int(os.getenv("YAWN_WINDOW_SECONDS", "60"))
    HEAD_TILT_DURATION_SECONDS: float = float(os.getenv("HEAD_TILT_DURATION_SECONDS", "3.0"))
    MICROSLEEP_DURATION_SECONDS: float = float(os.getenv("MICROSLEEP_DURATION_SECONDS", "2.0"))

    # ── Random Forest integration (TS-rf-integration) ────────────────
    RF_MODEL_PATH: str = os.getenv("RF_MODEL_PATH", "training/output/model.pkl")
    RF_FALLBACK_ENABLED: bool = os.getenv("RF_FALLBACK_ENABLED", "true").lower() == "true"

    # ── Camera capture (TS-service-merge) ──────────────────────────
    CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))
    FRAME_WIDTH: int = int(os.getenv("FRAME_WIDTH", "640"))
    FRAME_HEIGHT: int = int(os.getenv("FRAME_HEIGHT", "480"))
    JPEG_QUALITY: int = int(os.getenv("JPEG_QUALITY", "85"))
    MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", "2"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
