"""FastAPI application entry point for seatbelt-service.

Loads YOLO model and starts RabbitMQ messaging on startup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.seatbelt import router as seatbelt_router
from app.messaging.orchestrator import get_orchestrator
from app.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load YOLO model and start RabbitMQ on startup."""
    logger.info("Starting Seatbelt-Service...")
    orchestrator = get_orchestrator()
    orchestrator.start()
    logger.info("Seatbelt-Service ready")
    yield
    logger.info("Shutting down Seatbelt-Service...")
    orchestrator.stop()


app = FastAPI(
    title="Seatbelt Detection Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(seatbelt_router)
