import cv2
import time
import os
import numpy as np
import uvicorn
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse

# 1. Imports from vehicle_ai
from vehicle_core.detector import ObjectDetector
from vehicle_logic.risk_analyzer import RiskAnalyzer
from vehicle_utils.visualization import Visualizer
import vehicle_config

# 2. Imports from lane_ai
from lane_pipeline import LanePipeline

app = FastAPI(title="Unified ADAS Web Stream")

# Global instances (loaded once at startup)
print("="*60)
print(" INITIALIZING UNIFIED ADAS WEB SERVER")
print("="*60)
print("[1/2] Loading Vehicle AI Models (YOLOv11)...")
vehicle_detector = ObjectDetector()
risk_analyzer = RiskAnalyzer()

print("[2/2] Loading Lane AI Models (DeepLab + Hough)...")
lane_pipeline = LanePipeline()

# Tắt YOLO của LanePipeline vì vehicle_detector đã đảm nhận Tracking xe rồi
class DummyYOLO:
    def detect(self, frame): return []
lane_pipeline.yolo_detector = DummyYOLO() 

current_video_path = os.getenv("CAMERA_SOURCE", r"e:\Download_E\gopfile\CV\YTSave_YouTube_DSS-058-Video-Test-Camera-Hanh-Trinh-O-T_Media_L3ens063RmI_001_1080p.mp4")

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    global current_video_path
    os.makedirs("uploads", exist_ok=True)
    file_path = os.path.join("uploads", file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    current_video_path = file_path
    return {"status": "ok", "filename": file.filename}

from pydantic import BaseModel

class ConfigUpdate(BaseModel):
    warning_distance: float
    danger_distance: float

@app.post("/config")
async def update_config(config_data: ConfigUpdate):
    vehicle_config.WARNING_ZONE_DISTANCE = config_data.warning_distance
    vehicle_config.DANGER_ZONE_DISTANCE = config_data.danger_distance
    return {"status": "ok"}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Unified ADAS Live Stream</title>
    <style>
        body {
            background-color: #0b0c10;
            color: #66fcf1;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            background-image: radial-gradient(circle at 50% 50%, #1f2833 0%, #0b0c10 100%);
        }
        h1 { margin-bottom: 20px; font-weight: 400; letter-spacing: 3px; font-size: 2rem;}
        .video-container {
            border: 1px solid rgba(69, 162, 158, 0.3);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(69, 162, 158, 0.2);
            max-width: 90vw;
            max-height: 75vh;
            background: #000;
        }
        img { width: 100%; height: auto; display: block; max-height: 75vh; object-fit: contain; }
        .footer { margin-top: 15px; font-size: 0.9rem; opacity: 0.6; }
        .control-panel {
            margin-bottom: 20px; 
            background: rgba(31, 40, 51, 0.8); 
            padding: 15px 30px; 
            border-radius: 12px; 
            border: 1px solid rgba(69, 162, 158, 0.3);
            box-shadow: 0 5px 15px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: row;
            gap: 30px;
            align-items: flex-start;
        }
        .panel-section { display: flex; flex-direction: column; align-items: center; }
        button {
            background: #45a29e; color: white; border: none; padding: 10px 20px; 
            border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 1rem;
            transition: all 0.3s;
        }
        button:hover { background: #66fcf1; color: #0b0c10; }
        input[type="file"] { color: white; margin-bottom: 10px; font-size: 1rem; max-width: 250px; }
        
        .slider-container { display: flex; align-items: center; margin-bottom: 10px; justify-content: space-between; width: 300px; }
        .slider-container label { width: 150px; text-align: left; font-size: 0.9rem; font-weight: bold; color: #c5c6c7; }
        .slider-container input[type="range"] { flex-grow: 1; accent-color: #45a29e; }
        .slider-container span { width: 40px; text-align: right; color: #66fcf1; font-weight: bold; }
    </style>
</head>
<body>
    <h1>UNIFIED ADAS COMMAND CENTER</h1>
    
    <!-- Control Panel -->
    <div class="control-panel">
        <div class="panel-section">
            <h3 style="margin-top: 0; color: #c5c6c7; font-size: 1.1rem; border-bottom: 1px solid #45a29e; padding-bottom: 5px;">Upload Video</h3>
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" id="videoFile" name="file" accept="video/mp4,video/avi,video/mov">
                <br>
                <button type="submit">Upload & Scan</button>
            </form>
            <div id="uploadStatus" style="margin-top: 10px; color: #fca311; font-weight: bold; font-size: 0.9rem;"></div>
        </div>
        
        <div class="panel-section" style="border-left: 1px solid rgba(69,162,158,0.3); padding-left: 30px;">
            <h3 style="margin-top: 0; color: #c5c6c7; font-size: 1.1rem; border-bottom: 1px solid #45a29e; padding-bottom: 5px;">Danger Zones Setup</h3>
            <div class="slider-container">
                <label>Warning (Yellow):</label>
                <input type="range" id="warningSlider" min="15" max="50" value="22" step="1">
                <span id="warningVal">22m</span>
            </div>
            <div class="slider-container">
                <label>Danger (Red):</label>
                <input type="range" id="dangerSlider" min="3" max="20" value="8" step="1">
                <span id="dangerVal">8m</span>
            </div>
        </div>
    </div>

    <div class="video-container">
        <!-- Phát trực tiếp luồng MJPEG -->
        <img src="/stream" id="streamImg" alt="ADAS Live Stream">
    </div>
    <div class="footer">Real-time Multimodal AI Processing (Vehicle + Lane Detection)</div>

    <script>
        // --- Upload Logic ---
        document.getElementById('uploadForm').onsubmit = async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById('videoFile');
            const statusDiv = document.getElementById('uploadStatus');
            
            if (!fileInput.files[0]) {
                statusDiv.innerText = "Please select a video file first.";
                return;
            }
            
            statusDiv.innerText = "Uploading... Please wait.";
            
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            
            try {
                const response = await fetch("/upload", {
                    method: "POST",
                    body: formData
                });
                
                if (response.ok) {
                    statusDiv.innerText = "Switching stream...";
                    setTimeout(() => {
                        document.getElementById('streamImg').src = "/stream?t=" + new Date().getTime();
                        statusDiv.innerText = "Scanning: " + fileInput.files[0].name;
                    }, 1000);
                } else {
                    statusDiv.innerText = "Upload failed.";
                }
            } catch (err) {
                statusDiv.innerText = "Error: " + err.message;
            }
        };

        // --- Config Sliders Logic ---
        const warnSlider = document.getElementById('warningSlider');
        const dangSlider = document.getElementById('dangerSlider');
        const warnVal = document.getElementById('warningVal');
        const dangVal = document.getElementById('dangerVal');

        async function updateConfig() {
            const w_dist = parseFloat(warnSlider.value);
            const d_dist = parseFloat(dangSlider.value);
            warnVal.innerText = w_dist + "m";
            dangVal.innerText = d_dist + "m";

            // Prevent Danger from being > Warning
            if (d_dist >= w_dist) {
                dangSlider.value = w_dist - 1;
                dangVal.innerText = (w_dist - 1) + "m";
            }

            try {
                await fetch("/config", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        warning_distance: parseFloat(warnSlider.value),
                        danger_distance: parseFloat(dangSlider.value)
                    })
                });
            } catch (err) {
                console.error("Config update error", err);
            }
        }

        warnSlider.addEventListener('input', updateConfig);
        dangSlider.addEventListener('input', updateConfig);
    </script>
</body>
</html>
"""

@app.get("/")
def get_dashboard():
    """Trả về trang web chứa khung Video"""
    return HTMLResponse(content=HTML_PAGE)

def generate_frames():
    """Vòng lặp xử lý Video AI và phát stream JPEG"""
    global current_video_path
    last_played_path = None
    cap = None
    
    frame_id = 0
    prev_time = time.time()
    last_lane_overlay = None
    
    while True:
        # Check if user uploaded a new video
        if last_played_path != current_video_path:
            if cap is not None:
                cap.release()
            
            v_path = int(current_video_path) if str(current_video_path).isdigit() else current_video_path
            print(f"Switching stream to: {v_path}")
            cap = cv2.VideoCapture(v_path)
            last_played_path = current_video_path
            frame_id = 0
            
            if not cap.isOpened():
                print(f"Error opening video {current_video_path}")
                time.sleep(1)
                continue
                
        ret, frame = cap.read()
        if not ret:
            # Lặp lại video khi kết thúc
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
            
        # TỐI ƯU FPS MẠNH MẼ: Resize video xuống kích thước 800px để đẩy nhanh tốc độ quét AI
        h_orig, w_orig = frame.shape[:2]
        if w_orig > 800:
            frame = cv2.resize(frame, (800, int(800 * h_orig / w_orig)))
            
        frame_id += 1
        h, w = frame.shape[:2]
        
        # 1. LANE PIPELINE (Frame Skipping cực đại - chỉ chạy 1/6 số khung hình để giảm lag tối đa)
        if frame_id % 6 == 1:
            lane_results = lane_pipeline.process_frame(frame, visualize=True)
            last_lane_overlay = frame.copy()
        else:
            if last_lane_overlay is not None:
                frame[:] = last_lane_overlay[:]
            lane_results = {"direction": "UNKNOWN"}
            
        # 2. VEHICLE PIPELINE (Full Frames)
        results = vehicle_detector.track_objects(frame)
        boxes = np.array([])
        class_ids = np.array([])
        track_ids = np.array([])
        confidences = np.array([])
        
        if results.boxes is not None and len(results.boxes) > 0:
            raw_boxes = results.boxes.xyxy.cpu().numpy()
            raw_class_ids = results.boxes.cls.int().cpu().numpy()
            raw_confidences = results.boxes.conf.cpu().numpy()
            if results.boxes.id is not None:
                raw_track_ids = results.boxes.id.int().cpu().numpy()
            else:
                raw_track_ids = np.array([-1 - i for i in range(len(raw_boxes))])
                
            keep = vehicle_detector.filter_inside_vehicles(raw_boxes, raw_class_ids, raw_track_ids)
            boxes, track_ids, class_ids, confidences = raw_boxes[keep], raw_track_ids[keep], raw_class_ids[keep], raw_confidences[keep]
            
            keep_hood = vehicle_detector.filter_ego_car_hood(boxes, class_ids, track_ids, h, w)
            boxes, track_ids, class_ids, confidences = boxes[keep_hood], track_ids[keep_hood], class_ids[keep_hood], confidences[keep_hood]

        analysis_results = risk_analyzer.analyze_frame(
            frame, boxes, class_ids, track_ids, confidences, frame_id
        )
        
        # 3. DRAW COMBINED RESULTS
        output_frame = frame
        
        for k, obj in enumerate(analysis_results["objects"]):
            t_id = obj["track_id"]
            cls_id = int(class_ids[k])
            class_name = vehicle_config.CLASS_NAMES.get(cls_id, "Vật thể")
            display_id = "?" if t_id < 0 else str(t_id)
            Visualizer.draw_box_and_label(output_frame, obj["bbox_xyxy"], display_id, class_name, obj["distance"], obj["color"])
            
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if prev_time > 0 else 0
        prev_time = curr_time
        
        # Vẽ vùng cảnh báo 3D
        Visualizer.draw_zones(output_frame, h, w)
        
        Visualizer.draw_hud(output_frame, fps, analysis_results["global_risk_level"])
        
        lane_dir = lane_results.get("direction", "UNKNOWN")
        if lane_dir in ["LEFT", "RIGHT"]:
            cv2.putText(output_frame, f"LANE WARNING: {lane_dir}", (w//2 - 200, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 3, cv2.LINE_AA)

        # 4. ENCODE TO JPEG AND YIELD (Phát Stream)
        ret_enc, buffer = cv2.imencode('.jpg', output_frame)
        if ret_enc:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.get("/stream")
def stream_video():
    """Endpoint cung cấp luồng MJPEG liên tục"""
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8084))
    print(f"Bắt đầu Web Server. Truy cập http://localhost:{port}/ để xem Video Hợp Nhất.")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
