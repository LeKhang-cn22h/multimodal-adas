"""Gradio UI — reads from Orchestrator camera stream and inference results.

Provides a web interface showing real-time status and MJPEG stream.
"""

from __future__ import annotations

import time
import logging
import gradio as gr

from app.core.config import get_settings
from app.messaging.orchestrator import get_orchestrator
from app.utils.logger import get_logger

logger = get_logger()

# ── Pipeline State ───────────────────────────────────────────────────
_stream_active = False


def start_stream(source: str, fps: float = 30.0):
    """Start video/webcam capture in the Orchestrator's camera service."""
    global _stream_active
    logger.info("Gradio UI requested start stream with source: %s", source)
    _stream_active = True
    orchestrator = get_orchestrator()
    orchestrator.camera_service.start(source)


def stop_stream():
    """Stop capture in the Orchestrator's camera service."""
    global _stream_active
    logger.info("Gradio UI requested stop stream")
    _stream_active = False
    orchestrator = get_orchestrator()
    orchestrator.camera_service.stop()


def get_status() -> dict:
    """Return current status dictionary for API polling."""
    orchestrator = get_orchestrator()
    s = orchestrator.latest_result
    if s is None:
        return {
            "eye": "--", "eye_conf": 0.0, "mouth": "--",
            "mouth_conf": 0.0, "drowsiness": "NONE",
            "seatbelt": "--", "frame": 0, "fps": 0.0, "elapsed": 0.0,
        }

    settings = get_settings()
    
    # Extract values
    level = s.get("fatigue_level", "Unknown")
    
    features = s.get("features", {})
    ear = features.get("ear", 0.0)
    mar = features.get("mar", 0.0)
    
    eye_label = "CLOSED" if (0.0 < ear < settings.EAR_THRESHOLD) else "OPEN" if ear > 0.0 else "--"
    mouth_label = "YAWN" if mar > settings.MAR_THRESHOLD else "NO_YAWN" if mar > 0.0 else "--"
    
    has_sb = s.get("has_seatbelt", False)
    seatbelt_status = "ON" if has_sb else "OFF"
    
    frame_id = s.get("frame_id", 0)
    fps = orchestrator.camera_service.fps
    uptime = orchestrator.detector.get_stats().get("uptime", 0.0)

    return {
        "eye": eye_label,
        "eye_conf": ear,
        "mouth": mouth_label,
        "mouth_conf": mar,
        "drowsiness": level.upper(),
        "seatbelt": seatbelt_status,
        "frame": frame_id,
        "fps": fps,
        "elapsed": uptime,
    }


def _drowsiness_color(level: str) -> str:
    """Return background color for the given drowsiness level."""
    return {
        "Awake": "#2ecc71",       # Green
        "Tired": "#f1c40f",       # Yellow
        "Drowsy": "#e67e22",      # Orange
        "Dangerous": "#e74c3c",   # Red
        "Unknown": "#95a5a6",     # Grey
    }.get(level, "#95a5a6")


def build_ui() -> gr.Blocks:
    """Build the Gradio interface Blocks."""

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
                  /* Fixed-ratio box: video always fits inside */
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
                    object-fit: contain;
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
                    'UNKNOWN</div>'
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
            orchestrator = get_orchestrator()
            if not orchestrator.camera_service.is_running:
                return tuple([gr.update()] * 7)

            s = orchestrator.latest_result
            if s is None:
                return tuple([gr.update()] * 7)

            settings = get_settings()
            
            # Extract values
            level = s.get("fatigue_level", "Unknown")
            color = _drowsiness_color(level)
            
            features = s.get("features", {})
            ear = features.get("ear", 0.0)
            mar = features.get("mar", 0.0)
            
            eye_label = "CLOSED" if (0.0 < ear < settings.EAR_THRESHOLD) else "OPEN" if ear > 0.0 else "--"
            mouth_label = "YAWN" if mar > settings.MAR_THRESHOLD else "NO_YAWN" if mar > 0.0 else "--"
            
            has_sb = s.get("has_seatbelt", False)
            sb_conf = s.get("seatbelt_confidence")
            sb_conf_str = f" ({sb_conf:.2f})" if sb_conf is not None else ""
            seatbelt_status = "ON" if has_sb else "OFF"
            
            frame_id = s.get("frame_id", 0)
            fps = orchestrator.camera_service.fps
            
            # Elapsed time based on uptime stat
            uptime = orchestrator.detector.get_stats().get("uptime", 0.0)

            return (
                f'<div style="background:{color};padding:12px;border-radius:8px;'
                f'color:white;font-size:18px;font-weight:bold;text-align:center;">'
                f'{level.upper()}</div>',
                f'{eye_label} (EAR: {ear:.2f})',
                f'{mouth_label} (MAR: {mar:.2f})',
                ('<span style="color:#2ecc71;font-size:16px;">'
                 f'&#x2705; Seatbelt: {seatbelt_status}{sb_conf_str}</span>'
                 if seatbelt_status == "ON" else
                 '<span style="color:#e74c3c;font-size:16px;">'
                 f'&#x26D4; Seatbelt: {seatbelt_status}{sb_conf_str}</span>'),
                str(frame_id),
                f'{fps:.1f}',
                f'{uptime:.1f}s',
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