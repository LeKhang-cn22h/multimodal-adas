"""Gradio UI — same pipeline as app/demo/run_webcam_with_controls.py

MJPEG streaming + real-time status panel + stop / change video.
"""

from __future__ import annotations

import time
import threading

import cv2
import gradio as gr
import numpy as np

from app.config import EYE_MODEL, MOUTH_MODEL, SEATBELT_MODEL
from app.core.app_runtime_config import AppRuntimeConfig
from app.services.drowsiness_detector import DrowsinessDetector
from app.services.safety_monitor import SafetyMonitor
from app.services.seatbelt_detector import SeatbeltDetector
from app.services.voice_alert import get_voice_alert
from app.utils.logger import get_logger

logger = get_logger()

# ── Pipeline ──────────────────────────────────────────────────────────

_drowsiness: DrowsinessDetector | None = None
_seatbelt: SeatbeltDetector | None = None
_monitor: SafetyMonitor | None = None
_runtime_config: AppRuntimeConfig | None = None

# MJPEG stream
_stream_frame: bytes | None = None
_stream_lock = threading.Lock()
_stream_active = False
_stream_source: str = ""
_frame_idx: int = 0
_fps_source: float = 30.0
_alert_warmup: int = 90
_stream_thread: threading.Thread | None = None
_stream_cap: cv2.VideoCapture | None = None

# Cached overlay (updated by AI, applied by display)
_overlay_lock = threading.Lock()
_overlay_cache: dict = {}
_last_overlay_frame = None

# Shared buffer: latest raw frame for AI thread
_raw_frame_buf: np.ndarray | None = None
_ai_skip_count = 0  # count frames to skip AI


def _init_pipeline():
    global _drowsiness, _seatbelt, _monitor, _runtime_config
    if _monitor is not None:
        return
    _runtime_config = AppRuntimeConfig(
        drowsiness_enabled=True,
        seatbelt_enabled=True,
        seatbelt_check_every_n_frames=10,
    )
    _drowsiness = DrowsinessDetector(
        eye_model_path=str(EYE_MODEL),
        mouth_model_path=str(MOUTH_MODEL),
    )
    _seatbelt = SeatbeltDetector(model_path=str(SEATBELT_MODEL))
    _monitor = SafetyMonitor(
        drowsiness_detector=_drowsiness,
        seatbelt_detector=_seatbelt,
        runtime_config=_runtime_config,
    )


# =========================================================================
# MJPEG stream thread
# =========================================================================

def _stream_loop():
    """Single loop: read frames, process AI on subset, display all at source FPS."""
    global _stream_frame, _stream_active, _frame_idx, _stream_cap
    global _overlay_cache, _last_overlay_frame, _ai_skip_count

    t_start = time.time()

    try:
        _stream_cap = (cv2.VideoCapture(0) if _stream_source == "webcam"
                       else cv2.VideoCapture(_stream_source))
        cap = _stream_cap
        if not cap.isOpened():
            _stream_active = False
            return

        _init_pipeline()
        _frame_idx = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = 1.0 / max(fps, 1.0)
        t_next_display = time.time()
        last_ai_frame = None  # last frame processed by AI (with overlay)

        while _stream_active:
            ret, frame_bgr = cap.read()
            if not ret:
                if _stream_source != "webcam":
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    _frame_idx = 0
                    last_ai_frame = None
                    continue
                time.sleep(0.01)
                continue

            # ── AI processing: every frame, but skip if behind schedule ──
            now = time.time()
            behind = now > t_next_display + frame_interval * 0.5

            if not behind:
                try:
                    timestamp = _frame_idx / max(_fps_source, 1.0)
                    out_frame, result = _monitor.process(frame_bgr, timestamp=timestamp)

                    drowsiness = result.get("drowsiness") or {}
                    seatbelt = result.get("seatbelt") or {}
                    level = drowsiness.get("level")
                    has_sb = seatbelt.get("has_seatbelt")
                    eye = drowsiness.get("eye") or {}
                    mouth = drowsiness.get("mouth") or {}

                    # Voice alert
                    if _frame_idx > _alert_warmup:
                        va = get_voice_alert()
                        if va:
                            if level and level.value == "DROWSY":
                                va.alert_fatigue("Drowsy")
                            if has_sb is False:
                                va.alert_seatbelt(False)

                    # Resize
                    h, w = out_frame.shape[:2]
                    max_w, max_h = 800, 450
                    scale = min(max_w / w, max_h / h, 1.0)
                    if scale < 1.0:
                        out_frame = cv2.resize(out_frame, (int(w * scale), int(h * scale)))

                    last_ai_frame = out_frame

                    # Update status
                    elapsed = time.time() - t_start
                    with _overlay_lock:
                        _overlay_cache.update(
                            eye=eye.get("label", "--"),
                            eye_conf=eye.get("confidence", 0.0),
                            mouth=mouth.get("label", "--"),
                            mouth_conf=mouth.get("confidence", 0.0),
                            drowsiness=level.value if level else "NONE",
                            seatbelt="ON" if has_sb else "OFF",
                            frame=_frame_idx,
                            fps=round(_frame_idx / elapsed, 1) if elapsed > 0 else 0.0,
                            elapsed=round(elapsed, 1),
                        )
                except Exception:
                    pass  # AI error, keep last frame

            # ── Display: use last AI frame, or raw frame if none ──
            out = last_ai_frame if last_ai_frame is not None else frame_bgr
            if last_ai_frame is None:
                h, w = out.shape[:2]
                max_w, max_h = 800, 450
                scale = min(max_w / w, max_h / h, 1.0)
                if scale < 1.0:
                    out = cv2.resize(out, (int(w * scale), int(h * scale)))

            # ── Maintain FPS ──────────────────────────────────────
            sleep_time = t_next_display - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            t_next_display = time.time() + frame_interval

            # ── Send ──────────────────────────────────────────────
            _, jpeg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 92])
            with _stream_lock:
                _stream_frame = jpeg.tobytes()

            _frame_idx += 1

    except Exception as exc:
        logger.error("Stream error: %s", exc)
    finally:
        if _stream_cap is not None:
            _stream_cap.release()
            _stream_cap = None
        _stream_active = False


def start_stream(source: str, fps: float = 30.0):
    global _stream_source, _fps_source, _stream_active, _stream_thread
    global _overlay_cache, _last_overlay_frame
    stop_stream()
    _stream_source = source
    _fps_source = fps
    _stream_active = True
    with _overlay_lock:
        _overlay_cache = {}
        _last_overlay_frame = None
    _stream_thread = threading.Thread(
        target=_stream_loop, daemon=True, name="mjpeg-stream",
    )
    _stream_thread.start()


def stop_stream():
    global _stream_active, _stream_thread, _stream_cap
    _stream_active = False
    if _stream_cap is not None:
        try:
            _stream_cap.release()
        except Exception:
            pass
        _stream_cap = None
    if _stream_thread is not None and _stream_thread.is_alive():
        _stream_thread.join(timeout=0.5)


def get_stream_frame() -> bytes | None:
    with _stream_lock:
        return _stream_frame


def get_status() -> dict:
    with _overlay_lock:
        return dict(_overlay_cache) if _overlay_cache else {
            "eye": "--", "eye_conf": 0.0, "mouth": "--",
            "mouth_conf": 0.0, "drowsiness": "NONE",
            "seatbelt": "--", "frame": 0, "fps": 0.0, "elapsed": 0.0,
        }


# =========================================================================
# Gradio UI
# =========================================================================

def _drowsiness_color(level: str) -> str:
    return {
        "NORMAL": "#2ecc71", "DROWSY": "#e74c3c",
        "NO_FACE": "#e67e22", "FACE_DETECTED_BUT_INVALID": "#3498db",
        "NONE": "#95a5a6",
    }.get(level, "#95a5a6")


def build_ui() -> gr.Blocks:

    with gr.Blocks(title="Driver Safety Monitor", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🚗 Driver Safety Monitor")

        # ── Back button (shown when called from external system) ─────
        gr.HTML("""
        <div id="back-btn-container" style="display:none;margin-bottom:8px;">
          <button onclick="goBack()"
            style="padding:8px 20px;border:1px solid #aaa;border-radius:6px;
            background:#f5f5f5;cursor:pointer;font-size:14px;">
            ← Quay lại
          </button>
        </div>
        <script>
          const params = new URLSearchParams(window.location.search);
          const returnUrl = params.get('return_url');
          if (returnUrl) {
            document.getElementById('back-btn-container').style.display = 'block';
          }
          function goBack() {
            const p = new URLSearchParams(window.location.search);
            const url = p.get('return_url');
            if (url) window.location.href = url;
          }
        </script>
        """)

        # ── Controls ───────────────────────────────────────────────
        with gr.Row():
            btn_webcam = gr.Button("Bật Webcam", variant="primary")
            btn_video = gr.Button("Chọn Video", variant="secondary")
            btn_stop = gr.Button(" Dừng", variant="stop", visible=False)

        file_input = gr.File(
            label="Chọn file video",
            file_types=[".mp4", ".avi", ".mov", ".mkv", ".webm"],
            visible=False,
        )

        # ── Video + Zoom + Status ──────────────────────────────────

        with gr.Row():
            with gr.Column(scale=3, elem_id="video-col"):
                gr.HTML("""
                <style>
                  /* Fixed-ratio box: video always fits inside, never
                     stretches the page regardless of source aspect ratio. */
                  #video-box {
                    width: 100%;
                    max-width: 900px;
                    aspect-ratio: 16 / 9;
                    margin: 0 auto;
                    border-radius: 8px;
                    border: 2px solid #333;
                    background: #000;
                    overflow: hidden;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: max-width 0.3s;
                  }
                  #video-box.zoomed { max-width: 100%; }
                  #zoomable-video {
                    width: 100%;
                    height: 100%;
                    object-fit: contain;   /* keep aspect ratio, no crop, no overflow */
                    display: block;
                  }
                  .status-panel { transition:opacity 0.3s; }
                  .status-panel.hidden { display:none; }
                  #zoom-btn { margin-bottom:6px; padding:6px 16px; border:1px solid #aaa;
                    border-radius:6px; background:#f0f0f0; cursor:pointer; font-size:14px; }
                  #zoom-btn:hover { background:#ddd; }
                </style>
                <button id="zoom-btn" onclick="toggleZoom()"> Phóng to</button>
                <div id="video-box">
                  <img id="zoomable-video" src="/video_feed">
                </div>
                <script>
                  let zoomed = false;
                  function toggleZoom() {
                    zoomed = !zoomed;
                    document.getElementById('video-box').classList.toggle('zoomed', zoomed);
                    document.querySelectorAll('.status-panel').forEach(function(el) {
                      el.classList.toggle('hidden', zoomed);
                    });
                    document.getElementById('zoom-btn').textContent = zoomed ? '🔳 Thu nhỏ' : '🔲 Phóng to';
                  }
                </script>
                """)

            with gr.Column(scale=1, elem_classes="status-panel"):
                gr.Markdown("###  Status")
                drowsiness_html = gr.HTML(
                    '<div style="background:#95a5a6;padding:12px;border-radius:8px;'
                    'color:white;font-size:18px;font-weight:bold;text-align:center;">'
                    'NONE</div>'
                )
                eye_text = gr.Textbox(label="Eye", value="--", interactive=False)
                mouth_text = gr.Textbox(label="Mouth", value="--", interactive=False)
                seatbelt_html = gr.HTML(
                    '<span style="color:#95a5a6;font-size:16px;">Seatbelt: --</span>'
                )
                frame_text = gr.Textbox(label="Frame", value="0", interactive=False)
                fps_text = gr.Textbox(label="FPS", value="0.0", interactive=False)
                elapsed_text = gr.Textbox(label="Elapsed", value="0.0s", interactive=False)

        # ── Status timer ───────────────────────────────────────────
        def _refresh_status():
            if not _stream_active:
                return tuple([gr.update()] * 7)
            s = get_status()
            color = _drowsiness_color(s["drowsiness"])
            return (
                f'<div style="background:{color};padding:12px;border-radius:8px;'
                f'color:white;font-size:18px;font-weight:bold;text-align:center;">'
                f'{s["drowsiness"]}</div>',
                f'{s["eye"]} ({s["eye_conf"]:.0%})',
                f'{s["mouth"]} ({s["mouth_conf"]:.0%})',
                ('<span style="color:#2ecc71;font-size:16px;">'
                 f'&#x2705; Seatbelt: {s["seatbelt"]}</span>'
                 if s["seatbelt"] == "ON" else
                 '<span style="color:#e74c3c;font-size:16px;">'
                 f'&#x26D4; Seatbelt: {s["seatbelt"]}</span>'),
                str(s["frame"]),
                str(s["fps"]),
                f'{s["elapsed"]}s',
            )

        gr.Timer(0.3).tick(
            _refresh_status,
            outputs=[drowsiness_html, eye_text, mouth_text,
                     seatbelt_html, frame_text, fps_text, elapsed_text],
        )

        # ── Button handlers ────────────────────────────────────────

        def _start_webcam():
            start_stream("webcam")
            return (
                gr.update(visible=False),  # file_input
                gr.update(visible=True),   # btn_stop
            )

        def _show_picker():
            return (
                gr.update(visible=True),   # file_input
                gr.update(visible=False),  # btn_stop
            )

        def _start_video(file_obj):
            if file_obj is None:
                return (
                    gr.update(visible=True),   # file_input
                    gr.update(visible=False),  # btn_stop
                )
            path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
            start_stream(path)
            return (
                gr.update(visible=False),  # file_input
                gr.update(visible=True),   # btn_stop
            )

        def _stop():
            stop_stream()
            return (
                gr.update(visible=True),   # file_input
                gr.update(visible=False),  # btn_stop
            )

        btn_webcam.click(_start_webcam, outputs=[file_input, btn_stop])
        btn_video.click(_show_picker, outputs=[file_input, btn_stop])
        file_input.change(
            _start_video, inputs=[file_input],
            outputs=[file_input, btn_stop],
        )
        btn_stop.click(_stop, outputs=[file_input, btn_stop])

    return demo