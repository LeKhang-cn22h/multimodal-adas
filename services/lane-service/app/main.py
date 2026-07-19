import os
import sys
import shutil
import logging
import cv2
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# ── Đảm bảo thư mục app nằm trong Python path ────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import settings
from video_source import VideoSource
from pipeline import LanePipeline

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Kiểm tra ứng dụng đã đọc đúng config chưa
logger.info(f"Service Name : {settings.SERVICE_NAME if hasattr(settings, 'SERVICE_NAME') else 'lane-service'}")
logger.info(f"Port         : {settings.PORT}")
logger.info(f"Max Frames   : {settings.MAX_FRAMES}")

# ── Global Pipeline (Khởi tạo 1 lần duy nhất lúc start) ─────────────────────
logger.info("Dang khoi tao LanePipeline (YOLOv11 + DeepLab)...")
global_pipeline = LanePipeline()
logger.info("LanePipeline da san sang.")

# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="MULTIMODAL-ADAS Lane Service",
    version="2.0.0",
    description="ADAS lane detection service: YOLO + DeepLab + Sliding Window geometry",
)

# ── Static Dashboard (HTML/CSS/JS) ────────────────────────────────────────────
STATIC_DIR = os.path.join(APP_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Thư mục chứa video test ───────────────────────────────────────────────────
VIDEO_DIR = os.path.join(APP_DIR, "..", "data", "test_videos")
os.makedirs(VIDEO_DIR, exist_ok=True)

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".flv"}

# ── Trạng thái stream hiện tại ────────────────────────────────────────────────
current_stream_path: str = os.path.join(VIDEO_DIR, "solidWhiteRight.mp4")


# ── Helper functions ──────────────────────────────────────────────────────────

def set_active_video(video_path: str) -> None:
    """Thay đổi video đang phát MJPEG stream."""
    global current_stream_path
    current_stream_path = video_path
    logger.info(f"[Stream] Chuyen luong sang: {os.path.basename(video_path)}")


def analyze_video_file(
    video_path: str,
    filename: str = "video.mp4",
    max_frames: int = 30,
    pipeline: Optional[LanePipeline] = None,
) -> dict:
    """Chạy ADAS pipeline trên file video, trả về kết quả dict."""
    video_source = None
    try:
        logger.info(f"[Analyze] Bat dau xu ly: {filename} (max {max_frames} frames)")
        video_source = VideoSource(video_path)
        video_info = video_source.get_info()

        use_pipeline = pipeline or global_pipeline

        frames_processed = 0
        last_frame_result = None

        for frame in video_source.read_frames(max_frames=max_frames):
            last_frame_result = use_pipeline.process_frame(frame)
            frames_processed += 1

        logger.info(f"[Analyze] Hoan thanh: {frames_processed} frames | "
                    f"direction={last_frame_result.get('direction') if last_frame_result else 'N/A'}")

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


# ── Request/Response Models ───────────────────────────────────────────────────

class SetStreamRequest(BaseModel):
    filename: str


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    """Chuyển hướng về dashboard."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/ui", include_in_schema=False)
def dashboard():
    """Serve giao diện dashboard HTML."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health", tags=["System"])
def health():
    """Kiểm tra trạng thái dịch vụ."""
    return {"status": "ok", "service": "lane-service"}


@app.get("/videos", tags=["Video"])
def list_videos():
    """Trả về danh sách video có sẵn trong thư mục data/test_videos."""
    try:
        files = sorted([
            f for f in os.listdir(VIDEO_DIR)
            if os.path.splitext(f)[1].lower() in VIDEO_EXTS
        ])
        logger.info(f"[Videos] Tim thay {len(files)} video")
        return {"videos": files}
    except Exception as e:
        logger.error(f"[Videos] Loi doc thu muc: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/set-stream", tags=["Video"])
def set_stream(req: SetStreamRequest):
    """Chuyển video đang phát MJPEG stream."""
    logger.info(f"[SetStream] Nhan yeu cau chuyen sang: {req.filename}")

    video_path = os.path.join(VIDEO_DIR, req.filename)
    if not os.path.exists(video_path):
        logger.warning(f"[SetStream] Khong tim thay: {req.filename}")
        raise HTTPException(status_code=404, detail=f"Video not found: {req.filename}")

    set_active_video(video_path)
    return {"status": "ok", "filename": req.filename}


@app.post("/analyze-video", tags=["ADAS"])
async def analyze_video(file: UploadFile = File(...)):
    """
    Nhận video upload, chạy ADAS pipeline và trả về kết quả JSON.
    Đồng thời lưu video vào thư mục test_videos để dùng lại.
    """
    filename  = file.filename or "video.mp4"
    extension = os.path.splitext(filename)[1].lower()

    logger.info(f"[AnalyzeVideo] Nhan request: {filename} ({extension})")

    allowed_extensions = {".mp4", ".avi", ".mov", ".mkv"}
    if extension not in allowed_extensions:
        logger.warning(f"[AnalyzeVideo] Dinh dang khong hop le: {extension}")
        return Response(
            f"Chi ho tro dinh dang: {', '.join(allowed_extensions)}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Lưu file upload vào thư mục test_videos
        save_path = os.path.join(VIDEO_DIR, filename)
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"[AnalyzeVideo] Da luu video vao: {save_path}")

        # Chạy pipeline (CPU/GPU) trên threadpool để không block event loop
        result = await run_in_threadpool(
            analyze_video_file,
            save_path,
            filename=filename,
            max_frames=settings.MAX_FRAMES,
            pipeline=global_pipeline,
        )

        logger.info(f"[AnalyzeVideo] Thanh cong - {result['frames_processed']} frames")
        return result

    except ValueError as error:
        logger.error(f"[AnalyzeVideo] Loi gia tri: {error}")
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        logger.exception(f"[AnalyzeVideo] Loi xu ly: {error}")
        raise HTTPException(status_code=500, detail=f"Video processing error: {error}")
    finally:
        await file.close()


@app.get("/stream", tags=["ADAS"])
def stream_video():
    """MJPEG live stream của video đang active, đã qua ADAS pipeline overlay."""

    def generate_frames():
        import time
        last_video = None
        cap = None

        logger.info("[Stream] Bat dau phat MJPEG stream")
        while True:
            global current_stream_path
            if current_stream_path != last_video:
                if cap is not None:
                    cap.release()
                last_video = current_stream_path
                cap = cv2.VideoCapture(last_video)
                logger.info(f"[Stream] Mo video: {os.path.basename(last_video)}")

            if cap is None or not cap.isOpened():
                time.sleep(0.1)
                last_video = None
                continue

            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # Vẽ ADAS overlay (lane + YOLO)
            global_pipeline.process_frame(frame, visualize=True)

            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )

        if cap is not None:
            cap.release()

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── Local Test Runner ─────────────────────────────────────────────────────────

def run_local_test(video_path: str, max_frames: int = 30) -> None:
    """Chạy test nhanh 1 file video từ terminal, in kết quả ra console."""
    logger.info("=" * 60)
    logger.info(f"LOCAL TEST: {video_path}")
    logger.info("=" * 60)

    if not os.path.exists(video_path):
        logger.error(f"Khong tim thay file: {video_path}")
        return

    try:
        result = analyze_video_file(
            video_path,
            filename=os.path.basename(video_path),
            max_frames=max_frames,
            pipeline=global_pipeline,
        )
        last = result.get("last_frame_result") or {}
        logger.info(f"Trang thai     : {result['status']}")
        logger.info(f"Frames xu ly   : {result['frames_processed']}")
        logger.info(f"Phat hien      : {last.get('num_detections', 0)} vat can")
        logger.info(f"Lane offset    : {last.get('lane_offset')} m")
        logger.info(f"Direction      : {last.get('direction')}")
        logger.info("LOCAL TEST THANH CONG")
        logger.info("=" * 60)
    except Exception as e:
        logger.exception(f"Loi khi chay thu: {e}")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # Chạy test local: python main.py <video_path>
        run_local_test(sys.argv[1], max_frames=settings.MAX_FRAMES)
    else:
        # Khởi chạy Web server
        port = settings.PORT
        logger.info(f"Khoi chay ADAS Web App tren port {port}")
        logger.info(f"  Dashboard : http://localhost:{port}/ui")
        logger.info(f"  API Docs  : http://localhost:{port}/docs")
        logger.info(f"  Health    : http://localhost:{port}/health")
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
