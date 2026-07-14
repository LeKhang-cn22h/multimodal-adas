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
    logger.info("Starting Driver Service")

    orchestrator = get_orchestrator()

    try:
        orchestrator.start()
        logger.info("Driver Service Ready")
        yield

    finally:
        logger.info("Stopping Driver Service")
        orchestrator.stop()


app = FastAPI(
    title="Driver Monitoring Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(fatigue_router)
