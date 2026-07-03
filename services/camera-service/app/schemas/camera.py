"""Pydantic response schemas for camera-service API."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str = Field(default="healthy", description="Overall service status")
    camera: bool = Field(default=True, description="Whether the camera is active")


class CameraInfoResponse(BaseModel):
    """Response for GET /info with current frame metadata."""

    frame_id: int = Field(..., description="Sequential frame identifier")
    timestamp: float = Field(..., description="Unix timestamp of latest frame capture")
    width: int = Field(..., description="Frame width in pixels")
    height: int = Field(..., description="Frame height in pixels")
    fps: float = Field(..., description="Actual camera capture FPS")


class CameraStatsResponse(BaseModel):
    """Response for GET /stats with aggregated runtime statistics."""

    uptime: float = Field(..., description="Seconds since service startup")
    total_frames: int = Field(..., description="Total frames captured since startup")
    camera_fps: float = Field(..., description="Average camera FPS over lifetime")
