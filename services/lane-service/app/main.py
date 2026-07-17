import os
import sys
import shutil
import tempfile
import cv2
import uvicorn
import gradio as gr
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure app directory is in Python's search path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
# Also add parent directory to resolve relative imports
sys.path.insert(0, os.path.dirname(APP_DIR))

from config import settings
from video_source import VideoSource, HttpCameraSource
from pipeline import LanePipeline

# ── Data directories ──────────────────────────────────────────────────────────
VIDEO_DIR = os.path.join(APP_DIR, "..", "data", "test_videos")
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".flv"}

# ── Global Pipeline Instance (Loaded Once at Startup) ─────────────────────────
print("Loading LanePipeline (YOLOv11)...")
global_pipeline = LanePipeline()
print("LanePipeline loaded successfully.")

# ── FastAPI App ───────────────────────────────────────────────────────────────
# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="Lane Detection Service", version="2.0.0")

# ── Static Files (Dashboard HTML/CSS/JS) ──────────────────────────────────────
STATIC_DIR = os.path.join(APP_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Create test_videos directory if it doesn't exist
os.makedirs(VIDEO_DIR, exist_ok=True)


def analyze_video_file(
    video_path: str,
    filename: str = "video.mp4",
    max_frames: int = 30,
    pipeline: LanePipeline = None,
) -> dict:
    """Xử lý video qua LanePipeline và trả về kết quả dưới dạng dict."""
    video_source = None
    try:
        if video_path.startswith("http://") or video_path.startswith("https://"):
            video_source = HttpCameraSource(video_path)
        else:
            video_source = VideoSource(video_path)
        video_info = video_source.get_info()

        use_pipeline = pipeline or global_pipeline or LanePipeline()

        frames_processed = 0
        last_frame_result = None

        for frame in video_source.read_frames(max_frames=max_frames):
            last_frame_result = use_pipeline.process_frame(frame)
            frames_processed += 1

        return {
            "status": "ok",
            "service": "lane-service",
            "filename": filename,
            "video": video_info,
            "frames_processed": frames_processed,
            "last_frame_result": last_frame_result,
        }
    finally:
        if video_source:
            video_source.close()


# ── Active stream state ────────────────────────────────────────────────────────
current_stream_path = "1"


def set_active_video(video_path: str):
    global current_stream_path
    current_stream_path = video_path
    print(f"[Stream] Da chuyen luong sang: {video_path}")

# Mount Gradio Dashboard UI from ui.py
from ui import create_gradio_app
demo = create_gradio_app(analyze_video_file, set_active_video)
app = gr.mount_gradio_app(app, demo, path="/demo")


# ── API Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    mq_connected = global_pipeline.is_mq_connected
    yolo_loaded = global_pipeline.vehicle_detector is not None
    deeplab_loaded = global_pipeline.deeplab.has_weights
    
    status = "healthy" if (mq_connected and yolo_loaded) else "degraded"
    
    return {
        "status": status,
        "service": "lane-service",
        "rabbitmq": "connected" if mq_connected else "disconnected",
        "yolo_model": "loaded" if yolo_loaded else "failed",
        "deeplab_weights": "loaded" if deeplab_loaded else "using_opencv_fallback",
        "stream_source": current_stream_path
    }


latest_live_status = {}


@app.get("/stream")
def stream_video():
    """MJPEG live stream của video đang active, đã chạy qua ADAS pipeline."""
    def generate_frames():
        import time
        import requests
        import numpy as np
        global latest_live_status
        last_video = None
        cap = None
        is_http = False
        frame_counter = 0
        last_overlay = None   # Cache overlay từ frame trước để tái sử dụng
        
        # Initialize UDP socket for streaming to Dashboard
        import socket
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_dest = (settings.DASHBOARD_UDP_HOST, settings.DASHBOARD_UDP_PORT)
        
        while True:
            try:
                global current_stream_path
                if current_stream_path != last_video:
                    if cap is not None:
                        cap.release()
                        cap = None
                    last_video = current_stream_path
                    is_http = str(current_stream_path).startswith("http://") or str(current_stream_path).startswith("https://")
                    if not is_http:
                        try:
                            # Check if last_video can be parsed as an integer camera index
                            camera_idx = int(last_video)
                            cap = cv2.VideoCapture(camera_idx)
                        except ValueError:
                            # Otherwise open as local video file path
                            cap = cv2.VideoCapture(last_video)

                if is_http:
                    try:
                        r = requests.get(current_stream_path, timeout=0.5)
                        if r.status_code == 200:
                            nparr = np.frombuffer(r.content, np.uint8)
                            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            success = frame is not None
                        else:
                            success = False
                    except Exception:
                        success = False
                    if not success:
                        time.sleep(0.1)
                        continue
                else:
                    if cap is None or not cap.isOpened():
                        time.sleep(1.0)
                        last_video = None
                        continue

                    success, frame = cap.read()
                    if not success:
                        # For video files, loop back to the beginning; for camera, sleep and retry
                        try:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        except Exception:
                            pass
                        time.sleep(0.1) # Prevent high CPU utilization on frame read failures
                        continue

                # Frame skipping: chạy ADAS pipeline mỗi 2 frame để tăng FPS
                frame_counter += 1
                if frame_counter % 2 == 0:
                    latest_live_status = global_pipeline.process_frame(frame, visualize=True)
                    last_overlay = frame.copy()
                elif last_overlay is not None and last_overlay.shape == frame.shape:
                    frame[:] = last_overlay[:]
                else:
                    latest_live_status = global_pipeline.process_frame(frame, visualize=True)
                    last_overlay = frame.copy()

                ret, buffer = cv2.imencode(".jpg", frame)
                if not ret:
                    continue

                jpeg_bytes = buffer.tobytes()
                try:
                    # Send frame over UDP if size is within limits
                    if len(jpeg_bytes) < 65000:
                        udp_sock.sendto(jpeg_bytes, udp_dest)
                except Exception as udp_exc:
                    print(f"[UDP Stream] Send failed: {udp_exc}")

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
            except Exception as exc:
                print(f"[Stream Generator] Exception: {exc}")
                time.sleep(0.1)
                continue

        if cap is not None:
            cap.release()

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ── Local Tester Block ────────────────────────────────────────────────────────
def run_local_test(video_path: str, max_frames: int = 30):
    print("=" * 70)
    print(f"BAT DAU CHAY THU LOCAL: {video_path}")
    print("=" * 70)

    if not os.path.exists(video_path):
        print(f"LOI: Khong tim thay file: {video_path}")
        return

    try:
        result = analyze_video_file(
            video_path,
            filename=os.path.basename(video_path),
            max_frames=max_frames,
            pipeline=global_pipeline,
        )
        print(f"Trang thai: {result['status']}")
        print(f"Thong tin Video: {result['video']}")
        print(f"Da xu ly: {result['frames_processed']} frames")
        last_res = result["last_frame_result"]
        if last_res:
            print(f"So phat hien o Frame cuoi: {last_res.get('num_detections')}")
        print("=" * 70)
    except Exception as e:
        import traceback
        print(f"LOI khi chay thu: {e}")
        traceback.print_exc()


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        run_local_test(sys.argv[1], max_frames=settings.MAX_FRAMES)
    else:
        port = settings.PORT
        print(f"Khoi chay Web App tren port {port}...")
        print(f"  Dashboard:   http://localhost:{port}/ui")
        print(f"  API Docs:    http://localhost:{port}/docs")
        print(f"  Health:      http://localhost:{port}/health")
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
