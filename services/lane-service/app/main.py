import os
import sys
import shutil
import tempfile
import cv2
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import time
import httpx
from fastapi import Response

# Ensure app directory is in Python's search path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import settings
from video_source import VideoSource, HttpCameraSource
from pipeline import LanePipeline

# ── Global Pipeline Instance (Loaded Once at Startup) ─────────────────────────
print("Loading LanePipeline (YOLOv11)...")
global_pipeline = LanePipeline()
print("LanePipeline loaded successfully.")

# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="Lane Detection Service", version="2.0.0")

# ── Static Files (Dashboard HTML/CSS/JS) ──────────────────────────────────────
STATIC_DIR = os.path.join(APP_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Data directories ──────────────────────────────────────────────────────────
VIDEO_DIR = os.path.join(APP_DIR, "..", "data", "test_videos")
os.makedirs(VIDEO_DIR, exist_ok=True)

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".flv"}


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


# ── API Endpoints ─────────────────────────────────────────────────────────────
# @app.get("/health")
# def health():
#     return {"status": "ok", "service": "lane-service"}


@app.get("/health")
async def health(response: Response):
    """
    Health check endpoint focused strictly on YOLO model initialization.
    """
    is_healthy = False
    yolo_status = "unloaded"

    # Verify if the global pipeline exists and specifically contains the yolo_detector instance
    if global_pipeline is not None and hasattr(global_pipeline, 'yolo_detector'):
        if global_pipeline.yolo_detector is not None:
            yolo_status = "loaded"
            is_healthy = True

    # Return HTTP 503 if the core YOLO model failed to load
    if not is_healthy:
        response.status_code = 503  

    return {
        "service": "lane-service",
        "status": "healthy" if is_healthy else "unavailable",
        "timestamp": round(time.time(), 2),
        "components": {
            "yolo_model": yolo_status
        }
    }
# ── Active stream state ────────────────────────────────────────────────────────
current_stream_path = os.path.join(VIDEO_DIR, "solidWhiteRight.mp4")


def set_active_video(video_path: str):
    global current_stream_path
    current_stream_path = video_path
    print(f"[Stream] Da chuyen luong sang: {video_path}")


# ── API Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/ui")
def dashboard():
    """Serve dashboard HTML."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "service": "lane-service"}


@app.get("/videos")
def list_videos():
    """Trả về danh sách các video có sẵn trong thư mục data/test_videos."""
    try:
        files = sorted([
            f for f in os.listdir(VIDEO_DIR)
            if os.path.splitext(f)[1].lower() in VIDEO_EXTS
        ])
        return {"videos": ["Live Camera (camera-service)"] + files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SetStreamRequest(BaseModel):
    filename: str


@app.post("/set-stream")
def set_stream(req: SetStreamRequest):
    """Chuyển video đang phát MJPEG stream."""
    if req.filename == "Live Camera (camera-service)":
        set_active_video(settings.CAMERA_SERVICE_URL)
        return {"status": "ok", "filename": req.filename}

    if req.filename.startswith("http://") or req.filename.startswith("https://"):
        set_active_video(req.filename)
        return {"status": "ok", "filename": req.filename}

    video_path = os.path.join(VIDEO_DIR, req.filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video not found: {req.filename}")
    set_active_video(video_path)
    return {"status": "ok", "filename": req.filename}


@app.post("/analyze-video")
async def analyze_video(file: UploadFile = File(...)):
    filename = file.filename or "video.mp4"
    extension = os.path.splitext(filename)[1].lower()
    allowed_extensions = {".mp4", ".avi", ".mov", ".mkv"}

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(allowed_extensions)} video files are supported."
        )

    temp_path = None
    try:
        # Lưu file upload vào thư mục test_videos để sau dùng được
        save_path = os.path.join(VIDEO_DIR, filename)
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Chạy pipeline
        result = await run_in_threadpool(
            analyze_video_file,
            save_path,
            filename=filename,
            max_frames=settings.MAX_FRAMES,
            pipeline=global_pipeline,
        )
        return result
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Video processing error: {error}")
    finally:
        await file.close()


@app.get("/stream")
def stream_video():
    """MJPEG live stream của video đang active, đã chạy qua ADAS pipeline."""
    def generate_frames():
        import time
        import requests
        import numpy as np
        last_video = None
        cap = None
        is_http = False
        frame_counter = 0
        last_overlay = None   # Cache overlay từ frame trước để tái sử dụng
        while True:
            global current_stream_path
            if current_stream_path != last_video:
                if cap is not None:
                    cap.release()
                    cap = None
                last_video = current_stream_path
                is_http = current_stream_path.startswith("http://") or current_stream_path.startswith("https://")
                if not is_http:
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
                    time.sleep(0.1)
                    last_video = None
                    continue

                success, frame = cap.read()
                if not success:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

            # Frame skipping: chạy ADAS pipeline mỗi 2 frame để tăng FPS
            frame_counter += 1
            if frame_counter % 2 == 0:
                global_pipeline.process_frame(frame, visualize=True)
                last_overlay = frame.copy()
            elif last_overlay is not None:
                frame[:] = last_overlay[:]

            ret, buffer = cv2.imencode(".jpg", frame)
            if not ret:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

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
