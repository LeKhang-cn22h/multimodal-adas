"""API routes for seatbelt-service."""

from fastapi import APIRouter

from app.messaging.orchestrator import get_orchestrator
from app.schemas.seatbelt import (
    HealthResponse,
    SeatbeltCheckResponse,
    StatsResponse,
)

router = APIRouter(tags=["seatbelt"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service health including model status."""
    orchestrator = get_orchestrator()
    return HealthResponse(
        status="healthy" if orchestrator.detector.is_loaded else "degraded",
        model_loaded=orchestrator.detector.is_loaded,
        camera_reachable=True,
    )


@router.get("/check", response_model=SeatbeltCheckResponse)
def check_seatbelt() -> SeatbeltCheckResponse:
    """Return latest seatbelt detection state."""
    orchestrator = get_orchestrator()
    result = orchestrator.detector.get_latest_result()
    return SeatbeltCheckResponse(**result)


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    """Return aggregated detection statistics."""
    orchestrator = get_orchestrator()
    stats = orchestrator.detector.get_stats()
    return StatsResponse(**stats)
