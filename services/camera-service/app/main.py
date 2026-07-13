"""FastAPI application entry point for camera-service.

Initialises CameraManager on startup and gracefully releases it on shutdown.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.camera import router as camera_router
from app.services.camera_manager_instance import camera_manager
from app.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start CameraManager on startup, release on shutdown."""
    logger.info("Starting CameraManager...")
    camera_manager.start()
    yield
    logger.info("Shutting down CameraManager...")
    camera_manager.stop()


app = FastAPI(
    title="Camera Management Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(camera_router)
