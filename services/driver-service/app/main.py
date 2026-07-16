"""FastAPI application entry point for driver-service.

Initialises MediaPipe model, Gradio UI, Voice Alert, MJPEG stream.
"""

import asyncio
from contextlib import asynccontextmanager

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from app.api.fatigue import router as fatigue_router
from app.core.config import get_settings
from app.messaging.orchestrator import get_orchestrator
from app.services.voice_alert import VoiceAlertService, set_voice_alert
from app.ui.gradio_app import build_ui
from app.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Driver Service")

    import app.ui.gradio_app as gradio_ui

    settings = get_settings()
    orchestrator = get_orchestrator()

    # ── 1. Load AI models ────────────────────────────────────────────
    logger.info("Model path: %s", settings.MODEL_PATH)
    try:
        orchestrator.start()
    except Exception as exc:
        logger.error("CRITICAL: orchestrator.start() failed: %s", exc)

    # ── 2. Voice alert ───────────────────────────────────────────────
    voice_alert = VoiceAlertService(
        model_name=settings.TTS_MODEL_NAME,
        cooldown_seconds=settings.VOICE_COOLDOWN_SECONDS,
        device="cpu",
    )
    try:
        voice_alert.load_model()
    except Exception as exc:
        logger.warning("TTS model not available: %s", exc)
    set_voice_alert(voice_alert)

    logger.info("Driver Service Ready")
    try:
        yield
    finally:
        logger.info("Shutting down ...")
        gradio_ui.stop_stream()
        try:
            orchestrator.stop()
        except Exception:
            pass
        try:
            voice_alert.close()
        except Exception:
            pass
        set_voice_alert(None)
        logger.info("Shutdown complete")


app = FastAPI(
    title="Driver Monitoring Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(fatigue_router)


# ── MJPEG video feed ──────────────────────────────────────────────────

@app.get("/video_feed")
async def video_feed(request: Request):
    """MJPEG stream for <img src="/video_feed">."""
    import app.ui.gradio_app as gradio_ui

    _placeholder: bytes | None = None

    async def generate():
        nonlocal _placeholder
        try:
            while True:
                if await request.is_disconnected():
                    break
                frame = gradio_ui.get_stream_frame()
                if frame is None:
                    if _placeholder is None:
                        import cv2
                        import numpy as np
                        black = np.zeros((360, 640, 3), dtype=np.uint8)
                        cv2.putText(black, "Waiting for source...",
                                    (120, 190), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.8, (255, 255, 255), 2)
                        _, jpg = cv2.imencode(".jpg", black,
                                              [cv2.IMWRITE_JPEG_QUALITY, 80])
                        _placeholder = jpg.tobytes()
                    frame = _placeholder
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                if not gradio_ui._stream_active:
                    import asyncio
                    await asyncio.sleep(0.1)
        except (asyncio.CancelledError, GeneratorExit):
            pass  # clean shutdown — ignore
        except Exception:
            pass  # ignore other errors during shutdown

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── Mount Gradio UI at /ui ────────────────────────────────────────────
gradio_app = build_ui()
app = gr.mount_gradio_app(app, gradio_app, path="/ui")

logger.info("Gradio UI mounted at /ui")
