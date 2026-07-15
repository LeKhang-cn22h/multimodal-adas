from fastapi import FastAPI
import uvicorn
import os
import cv2
import threading
import time
import numpy as np
import logging

from core.detector import ObjectDetector
from logic.risk_analyzer import RiskAnalyzer
from api_client import send_alert_event
from utils.visualization import Visualizer
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vehicle-service")

app = FastAPI(title="Vehicle Detection Service", version="1.0.0")

# Trạng thái service
service_state = {
    "running": False,
    "camera_source": os.getenv("CAMERA_SOURCE", "0"),
    "last_fps": 0,
    "global_risk_level": "safe"
}

detector = None
risk_analyzer = None

def init_ai_core():
    global detector, risk_analyzer
    if detector is None:
        logger.info("Khởi tạo AI Core (ObjectDetector & RiskAnalyzer)...")
        detector = ObjectDetector()
        risk_analyzer = RiskAnalyzer()

def processing_loop():
    global detector, risk_analyzer
    
    init_ai_core()
    
    cam_src = service_state["camera_source"]
    if cam_src.isdigit():
        cam_src = int(cam_src)
        
    cap = cv2.VideoCapture(cam_src)
    if not cap.isOpened():
        logger.error(f"Không thể mở luồng camera {cam_src}")
        service_state["running"] = False
        return

    logger.info(f"Bắt đầu luồng xử lý nhận diện phương tiện từ nguồn: {cam_src}")
    frame_id = 0
    prev_time = time.time()
    
    while service_state["running"]:
        ret, frame = cap.read()
        if not ret:
            logger.warning("Mất kết nối luồng camera, đang thử kết nối lại...")
            time.sleep(2)
            cap = cv2.VideoCapture(cam_src)
            continue

        frame_id += 1
        h, w = frame.shape[:2]
        
        try:
            # 1. AI Core: Nhận diện & Tracking
            results = detector.track_objects(frame)
            
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
                    
                # Áp dụng các bộ lọc
                keep_indices = detector.filter_inside_vehicles(raw_boxes, raw_class_ids, raw_track_ids)
                boxes = raw_boxes[keep_indices]
                track_ids = raw_track_ids[keep_indices]
                class_ids = raw_class_ids[keep_indices]
                confidences = raw_confidences[keep_indices]
                
                keep_indices_hood = detector.filter_ego_car_hood(boxes, class_ids, track_ids, h, w)
                boxes = boxes[keep_indices_hood]
                track_ids = track_ids[keep_indices_hood]
                class_ids = class_ids[keep_indices_hood]
                confidences = confidences[keep_indices_hood]
                
                keep_indices_lane = detector.filter_outside_lane(boxes, class_ids, track_ids, h, w)
                boxes = boxes[keep_indices_lane]
                track_ids = track_ids[keep_indices_lane]
                class_ids = class_ids[keep_indices_lane]
                confidences = confidences[keep_indices_lane]
                
            # 2. Phân tích nguy cơ
            analysis_results = risk_analyzer.analyze_frame(
                frame, boxes, class_ids, track_ids, confidences, frame_id
            )
            
            # Cập nhật trạng thái
            curr_time = time.time()
            service_state["last_fps"] = 1 / (curr_time - prev_time) if prev_time > 0 else 0
            prev_time = curr_time
            service_state["global_risk_level"] = analysis_results["global_risk_level"]
            
            # --- DEBUG VIEW ---
            if os.getenv("SHOW_VIDEO", "1") == "1":
                output_frame = frame.copy()
                Visualizer.draw_zones(output_frame, h, w)
                
                for k, obj in enumerate(analysis_results["objects"]):
                    t_id = obj["track_id"]
                    cls_id = int(class_ids[k])
                    class_name = config.CLASS_NAMES.get(cls_id, "Vật thể")
                    display_id = "?" if t_id < 0 else str(t_id)
                    Visualizer.draw_box_and_label(output_frame, obj["bbox_xyxy"], display_id, class_name, obj["distance"], obj["color"])

                if analysis_results["camera_occluded"]:
                    cv2.rectangle(output_frame, (0, 0), (w, 50), (0, 0, 150), -1)
                    cv2.putText(output_frame, analysis_results["camera_status_msg"], (20, 35), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

                Visualizer.draw_hud(output_frame, service_state["last_fps"], analysis_results["global_risk_level"])
                
                cv2.imshow("Vehicle Service - Debug View", output_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("Thoát Debug View.")
                    service_state["running"] = False
                    break
            # ------------------
            
            # 3. Gửi cảnh báo nếu có nguy cơ cao
            if analysis_results["global_risk_level"] in ["high", "critical"]:
                send_alert_event(
                    risk_level=analysis_results["global_risk_level"],
                    alert_msg=analysis_results["global_alert_msg"],
                    objects_data=analysis_results["objects"]
                )
                
        except Exception as e:
            logger.error(f"Lỗi khi xử lý frame: {e}")
            
    cap.release()
    logger.info("Luồng xử lý đã dừng.")

@app.on_event("startup")
def startup_event():
    service_state["running"] = True
    # Khởi chạy luồng phân tích ở background
    thread = threading.Thread(target=processing_loop, daemon=True)
    thread.start()

@app.on_event("shutdown")
def shutdown_event():
    service_state["running"] = False

@app.get("/health")
def health():
    return {
        "status": "ok", 
        "service": "vehicle-service",
        "running": service_state["running"],
        "fps": round(service_state["last_fps"], 2),
        "current_risk": service_state["global_risk_level"]
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8004"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
