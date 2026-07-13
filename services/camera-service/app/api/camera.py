"""API routes for the camera-service."""

from fastapi import APIRouter
from fastapi.responses import Response

from app.schemas.camera import CameraInfoResponse, CameraStatsResponse, HealthResponse
from app.services.camera_manager_instance import camera_manager

router = APIRouter(tags=["camera"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service health status including camera state."""
    camera_active = camera_manager.is_running
    return HealthResponse(
        status="healthy" if camera_active else "degraded",
        camera=camera_active,
    )


@router.get("/frame")
def get_frame() -> Response:
    """Return the latest camera frame as a JPEG image.

    The JPEG is pre-encoded by the background capture thread, so this
    endpoint incurs zero encoding overhead per request.
    """
    jpeg_bytes = camera_manager.latest_jpeg
    if jpeg_bytes is None:
        return Response(
            content=b"",
            media_type="image/jpeg",
            status_code=204,
        )
    return Response(content=jpeg_bytes, media_type="image/jpeg")


@router.get("/info", response_model=CameraInfoResponse)
def get_info() -> CameraInfoResponse:
    """Return metadata about the current camera frame."""
    return CameraInfoResponse(
        frame_id=camera_manager.frame_id,
        timestamp=round(camera_manager.timestamp, 3),
        width=camera_manager.width,
        height=camera_manager.height,
        fps=round(camera_manager.fps, 2),
    )


@router.get("/stats", response_model=CameraStatsResponse)
def get_stats() -> CameraStatsResponse:
    """Return aggregated runtime statistics."""
    stats = camera_manager.get_stats()
    return CameraStatsResponse(**stats)
