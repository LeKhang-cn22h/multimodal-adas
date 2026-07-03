"""Pydantic response schemas for seatbelt-service API."""

from typing import Optional

from pydantic import BaseModel, Field


class DetectionItem(BaseModel):
    """A single detected object."""

    class_name: str = Field(..., description="Detected class name")
    class_id: int = Field(..., description="Numeric class id")
    confidence: float = Field(..., description="Detection confidence [0-1]")
    bbox: list[int] = Field(default_factory=list, description="Bounding box [x1, y1, x2, y2]")


class SeatbeltCheckResponse(BaseModel):
    """Response for GET /check with detection results."""

    seatbelt_detected: bool = Field(..., description="Whether seatbelt is visible")
    no_seatbelt_streak: int = Field(default=0, description="Consecutive frames without seatbelt")
    warning: bool = Field(default=False, description="Warning state after threshold exceeded")
    detections: list[DetectionItem] = Field(default_factory=list, description="All detections in frame")
    timestamp: float = Field(..., description="Unix timestamp of the check")
    inference_time_ms: float = Field(default=0.0, description="YOLO inference duration in ms")


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str = Field(default="healthy", description="Service health status")
    model_loaded: bool = Field(default=True, description="Whether YOLO model is loaded")
    camera_reachable: bool = Field(default=True, description="Whether camera-service is reachable")


class StatsResponse(BaseModel):
    """Response for GET /stats."""

    uptime: float = Field(..., description="Seconds since service startup")
    total_checks: int = Field(..., description="Total /check calls served")
    seatbelt_ok_count: int = Field(default=0, description="Frames with seatbelt detected")
    seatbelt_missing_count: int = Field(default=0, description="Frames without seatbelt")
    avg_inference_ms: float = Field(default=0.0, description="Average inference time in ms")
