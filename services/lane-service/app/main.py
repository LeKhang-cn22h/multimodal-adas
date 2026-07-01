from fastapi import FastAPI, File, HTTPException, UploadFile
import gradio as gr
import os
import shutil
import tempfile
import uvicorn

from video_source import VideoSource
from pipeline import LanePipeline
from ui import create_gradio_app


app = FastAPI(title="Lane Detection Service", version="1.0.0")


def analyze_video_file(video_path: str, filename: str = "video.mp4", max_frames: int = 30) -> dict:
    video_source = None

    try:
        video_source = VideoSource(video_path)
        video_info = video_source.get_info()

        pipeline = LanePipeline()

        frames_processed = 0
        last_frame_result = None

        for frame in video_source.read_frames(max_frames=max_frames):
            last_frame_result = pipeline.process_frame(frame)
            frames_processed += 1

        return {
            "status": "ok",
            "service": "lane-service",
            "filename": filename,
            "message": "Video read successfully. Lane pipeline has processed video frames.",
            "video": video_info,
            "frames_processed": frames_processed,
            "last_frame_result": last_frame_result,
        }

    finally:
        if video_source:
            video_source.close()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "lane-service"
    }


@app.post("/analyze-video")
async def analyze_video(file: UploadFile = File(...)):
    filename = file.filename or "video.mp4"
    extension = os.path.splitext(filename)[1].lower()

    allowed_extensions = {".mp4", ".avi", ".mov", ".mkv"}

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only .mp4, .avi, .mov, and .mkv video files are supported."
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name

        result = analyze_video_file(
            video_path=temp_path,
            filename=filename,
            max_frames=30
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Video processing error: {error}"
        )

    finally:
        await file.close()

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


gradio_app = create_gradio_app(analyze_video_file)

app = gr.mount_gradio_app(
    app,
    gradio_app,
    path="/ui"
)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)