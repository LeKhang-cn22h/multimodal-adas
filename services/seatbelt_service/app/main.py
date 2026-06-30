"""FastAPI application entry point for seatbelt-service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.seatbelt import router as seatbelt_router
from app.services.detector_instance import detector
from app.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load YOLO model on startup."""
    logger.info("Loading YOLO model...")
    detector.load_model()
    logger.info("Seatbelt service ready")
    yield
    logger.info("Seatbelt service shutting down")


app = FastAPI(
    title="Seatbelt Detection Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(seatbelt_router)
