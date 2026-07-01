import os
import sys
import shutil
import cv2
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

# Ensure app directory is in Python's search path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from config import settings

app = FastAPI(title="Video Service", version="1.0.0")

# Đảm bảo thư mục lưu trữ video tồn tại
os.makedirs(settings.STORAGE_DIR, exist_ok=True)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "video-service"
    }


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ.")
        
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = {".mp4", ".avi", ".mov", ".mkv"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400, 
            detail=f"Chỉ chấp nhận các định dạng video: {', '.join(allowed_exts)}"
        )
        
    save_path = os.path.join(settings.STORAGE_DIR, filename)
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_size = os.path.getsize(save_path)
        return {
            "status": "success",
            "filename": filename,
            "size_bytes": file_size,
            "url": f"/videos/{filename}",
            "stream_url": f"/videos/{filename}/stream"
        }
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu file: {e}")
    finally:
        await file.close()


@app.get("/videos")
def list_videos():
    try:
        files = os.listdir(settings.STORAGE_DIR)
        video_list = []
        for f in files:
            if f.startswith("."):
                continue
            path = os.path.join(settings.STORAGE_DIR, f)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                video_list.append({
                    "filename": f,
                    "size_bytes": size,
                    "url": f"/videos/{f}",
                    "stream_url": f"/videos/{f}/stream"
                })
        return {"videos": video_list, "total_count": len(video_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/videos/{filename}")
def get_video_file(filename: str):
    file_path = os.path.join(settings.STORAGE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file video.")
    # FileResponse tự động hỗ trợ range-headers (cho phép tua)
    return FileResponse(file_path, media_type="video/mp4")


@app.get("/videos/{filename}/stream")
def stream_video_frames(filename: str):
    file_path = os.path.join(settings.STORAGE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file video.")
        
    def generate_frames():
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return
            
        while True:
            success, frame = cap.read()
            if not success:
                break
                
            # Mã hóa khung hình sang định dạng JPEG
            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                continue
                
            frame_bytes = jpeg.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                   
        cap.release()

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    port = settings.PORT
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
