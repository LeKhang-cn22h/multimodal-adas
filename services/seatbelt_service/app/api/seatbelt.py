"""API routes for seatbelt-service."""

from fastapi import APIRouter

from app.schemas.seatbelt import (
    HealthResponse,
    SeatbeltCheckResponse,
    StatsResponse,
)
from app.services.detector_instance import detector

router = APIRouter(tags=["seatbelt"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service health including model and camera status."""
    return HealthResponse(
        status="healthy" if detector.is_loaded else "degraded",
        model_loaded=detector.is_loaded,
        camera_reachable=True,
    )


@router.get("/check", response_model=SeatbeltCheckResponse)
def check_seatbelt() -> SeatbeltCheckResponse:
    """Fetch a frame from camera-service and run seatbelt detection.

    Called periodically (e.g. every 3 seconds) by external services
    or the monitoring dashboard.
    """
    result = detector.check_frame()
    return SeatbeltCheckResponse(**result)


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    """Return aggregated detection statistics."""
    stats = detector.get_stats()
    return StatsResponse(**stats)
