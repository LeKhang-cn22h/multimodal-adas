import os
import sys
import shutil
import tempfile
import cv2
import uvicorn
import gradio as gr
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

# Ensure app directory is in Python's search path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import settings
from video_source import VideoSource
from pipeline import LanePipeline
from ui import create_gradio_app

# ── Global Pipeline Instance (Loaded Once at Startup) ─────────────────────────
print("Loading LanePipeline (YOLOv11)...")
global_pipeline = LanePipeline()
print("LanePipeline loaded successfully.")

# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="Lane Detection Service", version="1.0.0")


def analyze_video_file(
    video_path: str,
    filename: str = "video.mp4",
    max_frames: int = 30,
    pipeline: LanePipeline = None,
) -> dict:
    """Xử lý video qua LanePipeline và trả về kết quả dưới dạng dict."""
    video_source = None
    try:
        video_source = VideoSource(video_path)
        video_info = video_source.get_info()

        # Tái sử dụng pipeline truyền vào, hoặc dùng global_pipeline, hoặc tạo mới nếu chưa có
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
@app.get("/health")
def health():
    return {"status": "ok", "service": "lane-service"}


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
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name

        # Chạy tác vụ đồng bộ nặng (CPU/GPU) trên threadpool phụ của FastAPI để tránh blocking
        result = await run_in_threadpool(
            analyze_video_file,
            temp_path,
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
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/stream")
def stream_video():
    """Endpoint cung cấp MJPEG live stream của video đã chạy qua pipeline (YOLO + Lane Overlay)."""
    video_path = os.path.join(APP_DIR, "..", "data", "test_videos", "solidWhiteRight.mp4")
    
    def generate_frames():
        while True:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                break
                
            while True:
                success, frame = cap.read()
                if not success:
                    break
                
                # Chạy pipeline vẽ đè kết quả trực quan (visualize=True)
                global_pipeline.process_frame(frame, visualize=True)
                
                # Mã hóa JPEG
                ret, buffer = cv2.imencode(".jpg", frame)
                if not ret:
                    continue
                    
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                       
            cap.release()
            
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ── Mount Gradio UI ───────────────────────────────────────────────────────────
def gradio_analyze_wrapper(video_path: str, filename: str = "video.mp4", max_frames: int = 30) -> dict:
    if not video_path:
        return {"error": "No video provided."}
    return analyze_video_file(
        video_path=video_path,
        filename=filename,
        max_frames=max_frames,
        pipeline=global_pipeline,
    )

gradio_app = create_gradio_app(gradio_analyze_wrapper)
app = gr.mount_gradio_app(app, gradio_app, path="/ui")


# ── Local Tester Block ────────────────────────────────────────────────────────
def run_local_test(video_path: str, max_frames: int = 30):
    """Chạy test local một video và in kết quả ra terminal."""
    print("=" * 70)
    print(f"BẮT ĐẦU CHẠY THỬ LOCAL: {video_path}")
    print("=" * 70)
    
    if not os.path.exists(video_path):
        print(f"LỖI: Không tìm thấy file: {video_path}")
        return
        
    try:
        result = analyze_video_file(
            video_path,
            filename=os.path.basename(video_path),
            max_frames=max_frames,
            pipeline=global_pipeline,
        )
        print(f"Trạng thái: {result['status']}")
        print(f"Thông tin Video: {result['video']}")
        print(f"Đã xử lý: {result['frames_processed']} frames")
        
        last_res = result["last_frame_result"]
        if last_res:
            print(f"Số lượng phát hiện ở Frame cuối: {last_res.get('num_detections')}")
            for i, det in enumerate(last_res.get("detections", [])):
                print(f"  [{i+1}] {det['class_name']} ({det['confidence']*100:.1f}%) -> bbox: {det['bbox']}")
        print("=" * 70)
        print("CHẠY THỬ LOCAL THÀNH CÔNG!")
        print("=" * 70)
    except Exception as e:
        import traceback
        print(f"LỖI khi chạy thử: {e}")
        traceback.print_exc()


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Nếu truyền file video qua dòng lệnh: python main.py <video_path>
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        video_arg = sys.argv[1]
        run_local_test(video_arg, max_frames=settings.MAX_FRAMES)
    else:
        # Mặc định khởi chạy Web App (FastAPI + Gradio)
        port = settings.PORT
        print(f"Khởi chạy Web App trên port {port}...")
        print(f"  Gradio UI (Giao diện web): http://localhost:{port}/ui")
        print(f"  API Docs (Swagger):        http://localhost:{port}/docs")
        print(f"  Health Check:               http://localhost:{port}/health")
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
