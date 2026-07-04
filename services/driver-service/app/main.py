"""FastAPI application entry point for driver-service.

Initialises MediaPipe model and RabbitMQ messaging on startup,
gracefully releases on shutdown.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.fatigue import router as fatigue_router
from app.messaging.orchestrator import get_orchestrator
from app.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load MediaPipe model and start RabbitMQ on startup."""
    logger.info("Starting Driver-Service...")
    orchestrator = get_orchestrator()
    orchestrator.start()
    logger.info("Driver-Service ready")
    yield
    logger.info("Shutting down Driver-Service...")
    orchestrator.stop()


app = FastAPI(
    title="Driver Monitoring Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(fatigue_router)
