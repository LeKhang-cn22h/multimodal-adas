"""API routes for driver-service."""

from fastapi import APIRouter

from app.messaging.orchestrator import get_orchestrator

router = APIRouter(tags=["driver"])


@router.get("/health")
def health():
    """Return service health status."""
    orchestrator = get_orchestrator()
    return {
        "status": "healthy" if orchestrator.detector.is_loaded else "degraded",
        "service": "driver-service",
        "model_loaded": orchestrator.detector.is_loaded,
    }


@router.get("/stats")
def stats():
    """Return drowsiness detection statistics."""
    orchestrator = get_orchestrator()
    return orchestrator.detector.get_stats()
