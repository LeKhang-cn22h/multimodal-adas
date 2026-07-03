"""Message schemas for RabbitMQ communication."""

from typing import Optional

from pydantic import BaseModel, Field


class FrameMessage(BaseModel):
    """Metadata attached as AMQP headers when publishing a frame.

    The frame body is raw JPEG bytes.
    """

    frame_id: int = Field(..., description="Sequential frame identifier")
    timestamp: float = Field(..., description="Unix timestamp of frame capture")


class DriverResultMessage(BaseModel):
    """Result produced by Driver-Service after drowsiness inference."""

    frame_id: int = Field(..., description="Frame id this result corresponds to")
    timestamp: float = Field(..., description="Unix timestamp of inference")
    sleepy: bool = Field(default=False, description="Whether driver is drowsy")
    confidence: float = Field(default=0.0, description="Confidence score [0-1]")


class SeatbeltResultMessage(BaseModel):
    """Result produced by Seatbelt-Service after YOLO inference."""

    frame_id: int = Field(..., description="Frame id this result corresponds to")
    timestamp: float = Field(..., description="Unix timestamp of inference")
    seatbelt: bool = Field(default=False, description="Whether seatbelt is detected")
    confidence: float = Field(default=0.0, description="Confidence score [0-1]")
