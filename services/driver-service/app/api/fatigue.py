"""API routes for driver-service — monitoring control + diagnostics."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.messaging.orchestrator import get_orchestrator
from app.ui.gradio_app import (
    start_stream,
    stop_stream,
    get_status,
    _stream_active,
)

router = APIRouter(tags=["driver"])


# ── Schemas ───────────────────────────────────────────────────────────

class MonitorStartRequest(BaseModel):
    source: str = "webcam"  # "webcam" or path to video file
    fps: float = 30.0


# ── Health / Stats / Frame (existing) ─────────────────────────────────

@router.get("/health")
def health():
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
    orchestrator = get_orchestrator()
    detector_stats = orchestrator.detector.get_stats()
    camera = orchestrator.camera_service
    detector_stats["camera_fps"] = camera.fps
    detector_stats["camera_dropped_frames"] = camera.dropped_frames
    return detector_stats


@router.get("/frame")
def get_frame():
    orchestrator = get_orchestrator()
    jpeg = orchestrator.camera_service.latest_jpeg
    if jpeg is None:
        return Response(
            content=b"",
            status_code=503,
            headers={"X-Error": "Camera not ready"},
        )
    return Response(content=jpeg, media_type="image/jpeg")


# ── Monitor Control API (cho external frontend gọi) ───────────────────

@router.post("/monitor/start")
def monitor_start(req: MonitorStartRequest):
    """Bắt đầu monitoring. Gọi từ frontend ngoài.

    Body: {"source": "webcam"} hoặc {"source": "video", "path": "..."}
    Returns: {"status": "started", "video_feed_url": "/video_feed"}
    """
    if _stream_active:
        stop_stream()

    source = req.source if req.source else "webcam"
    start_stream(source, fps=req.fps)

    return {
        "status": "started",
        "source": source,
        "video_feed_url": "/video_feed",
    }


@router.post("/monitor/stop")
def monitor_stop():
    """Dừng monitoring."""
    was_active = _stream_active
    stop_stream()
    return {
        "status": "stopped",
        "was_active": was_active,
    }


@router.get("/monitor/status")
def monitor_status():
    """Trả về trạng thái monitoring hiện tại (cho polling)."""
    s = get_status()
    return {
        "active": _stream_active,
        "drowsiness": s.get("drowsiness", "NONE"),
        "eye": s.get("eye", "--"),
        "eye_confidence": s.get("eye_conf", 0.0),
        "mouth": s.get("mouth", "--"),
        "mouth_confidence": s.get("mouth_conf", 0.0),
        "seatbelt": s.get("seatbelt", "--"),
        "frame": s.get("frame", 0),
        "fps": s.get("fps", 0.0),
        "elapsed": s.get("elapsed", 0.0),
    }
