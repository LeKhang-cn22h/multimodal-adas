<<<<<<< HEAD
"""API routes for driver-service."""

from fastapi import APIRouter
from fastapi.responses import Response

from app.messaging.orchestrator import get_orchestrator

router = APIRouter(tags=["driver"])


@router.get("/health")
def health():
    """Return service health status."""
    orchestrator = get_orchestrator()
    camera = orchestrator.camera_service
    return {
        "status": (
            "healthy"
            if orchestrator.landmark_service.is_loaded and camera.is_running
            else "degraded"
        ),
        "service": "driver-service",
        "model_loaded": orchestrator.landmark_service.is_loaded,
        "classification_method": orchestrator.detector.classification_method,
        "camera_connected": camera.is_running,
    }


@router.get("/stats")
def stats():
    """Return drowsiness detection + camera statistics."""
    orchestrator = get_orchestrator()
    detector_stats = orchestrator.detector.get_stats()
    camera = orchestrator.camera_service

    detector_stats["camera_fps"] = camera.fps
    detector_stats["camera_dropped_frames"] = camera.dropped_frames
    return detector_stats


@router.get("/frame")
def get_frame():
    """Return the latest JPEG frame from webcam (debug endpoint)."""
    orchestrator = get_orchestrator()
    jpeg = orchestrator.camera_service.latest_jpeg
    if jpeg is None:
        return Response(
            content=b"",
            status_code=503,
            headers={"X-Error": "Camera not ready or no frame captured yet"},
        )
    return Response(content=jpeg, media_type="image/jpeg")
=======
>>>>>>> origin/lane-vehicle_service
