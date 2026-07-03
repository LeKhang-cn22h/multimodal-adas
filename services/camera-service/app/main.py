"""FastAPI application entry point for camera-service.

Initialises CameraManager and RabbitMQ messaging on startup,
gracefully releases on shutdown.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.camera import router as camera_router
from app.messaging.orchestrator import get_orchestrator
from app.services.camera_manager_instance import camera_manager
from app.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start CameraManager + RabbitMQ messaging on startup, release on shutdown."""
    logger.info("Starting CameraManager...")
    camera_manager.start()

    logger.info("Starting RabbitMQ messaging...")
    orchestrator = get_orchestrator()
    orchestrator.start()

    yield

    logger.info("Shutting down RabbitMQ messaging...")
    orchestrator.stop()

    logger.info("Shutting down CameraManager...")
    camera_manager.stop()


app = FastAPI(
    title="Camera Management Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(camera_router)
