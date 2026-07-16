from fastapi import FastAPI
import uvicorn
import os
import cv2
import threading
import time
import numpy as np
import logging
import sys
import grpc
from concurrent import futures

# Ensure app and app/protos are in python search path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROTOS_DIR = os.path.join(APP_DIR, "protos")
if PROTOS_DIR not in sys.path:
    sys.path.insert(0, PROTOS_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import adas_pb2
import adas_pb2_grpc
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
    "current_risk": "safe"
}

detector = None
risk_analyzer = None
grpc_server = None

# Cache lưu trữ nhận diện cho frame chẵn/lẻ để tăng gấp đôi FPS
last_detection_cache = {
    "boxes": np.array([]),
    "class_ids": np.array([]),
    "track_ids": np.array([]),
    "confidences": np.array([])
}

def init_ai_core():
    global detector, risk_analyzer
    if detector is None:
        logger.info("Khởi tạo AI Core (ObjectDetector & RiskAnalyzer)...")
        detector = ObjectDetector()
        risk_analyzer = RiskAnalyzer()

class VehicleAnalysisServicer(adas_pb2_grpc.VehicleAnalysisServiceServicer):
    def AnalyzeFrame(self, request, context):
        global detector, risk_analyzer
        init_ai_core()
        
        t0 = time.time()
        
        # 1. Giải mã ảnh JPEG nhận được từ gRPC
        np_arr = np.frombuffer(request.image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if frame is None:
            logger.warning(f"[gRPC] Giải mã ảnh thất bại cho frame_id {request.frame_id}")
            return adas_pb2.VehicleResponse(
                frame_id=request.frame_id,
                timestamp=request.timestamp,
                risk_level="safe",
                alert_msg="Lỗi giải mã ảnh",
                camera_occluded=False
            )
            
        h, w = frame.shape[:2]
        
        # Quyết định chạy YOLO hay lấy từ cache (chạy cách khung hình - chẵn chạy YOLO, lẻ lấy cache)
        should_run_yolo = (request.frame_id % 2 == 0) or (len(last_detection_cache["boxes"]) == 0)
        
        try:
            if should_run_yolo:
                # 2. Nhận diện & Tracking vật thể bằng YOLOv11
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
                        
                    # Áp dụng bộ lọc hình học
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
                
                # Cập nhật cache lưu trữ
                last_detection_cache["boxes"] = boxes
                last_detection_cache["class_ids"] = class_ids
                last_detection_cache["track_ids"] = track_ids
                last_detection_cache["confidences"] = confidences
            else:
                # Phục hồi dữ liệu từ cache cho frame lẻ
                boxes = last_detection_cache["boxes"]
                class_ids = last_detection_cache["class_ids"]
                track_ids = last_detection_cache["track_ids"]
                confidences = last_detection_cache["confidences"]
                
            # 3. Phân tích nguy cơ va chạm
            analysis_results = risk_analyzer.analyze_frame(
                frame, boxes, class_ids, track_ids, confidences, request.frame_id
            )
            
            # Cập nhật trạng thái
            service_state["current_risk"] = analysis_results["global_risk_level"]
            
            # 4. Gửi cảnh báo về Aggregator qua HTTP POST nếu nguy hiểm cao
            if analysis_results["global_risk_level"] in ["high", "critical"]:
                send_alert_event(
                    risk_level=analysis_results["global_risk_level"],
                    alert_msg=analysis_results["global_alert_msg"],
                    objects_data=analysis_results["objects"]
                )
                
            # 5. Đóng gói danh sách vật thể gửi trả về Client qua gRPC
            proto_objects = []
            for k, obj in enumerate(analysis_results["objects"]):
                t_id = obj["track_id"]
                cls_id = int(class_ids[k]) if k < len(class_ids) else -1
                class_name = config.CLASS_NAMES.get(cls_id, "Vật thể")
                
                # Ánh xạ từ tuple BGR sang chuỗi màu string để gRPC không bị lỗi kiểu dữ liệu
                color_val = obj["color"]
                if color_val == config.COLOR_DANGER:
                    color_str = "red"
                elif color_val == config.COLOR_WARNING:
                    color_str = "orange"
                else:
                    color_str = "green"
                
                det_obj = adas_pb2.DetectedObject(
                    track_id=int(t_id),
                    class_name=str(class_name),
                    distance=float(obj["distance"]),
                    color=str(color_str)
                )
                det_obj.bbox.extend([float(x) for x in obj["bbox_xyxy"]])
                proto_objects.append(det_obj)
            
            elapsed_ms = (time.time() - t0) * 1000.0
            logger.info(f"[gRPC] Da xu ly frame {request.frame_id} trong {elapsed_ms:.1f}ms. Phat hien {len(proto_objects)} xe.")
            
            return adas_pb2.VehicleResponse(
                frame_id=request.frame_id,
                timestamp=request.timestamp,
                risk_level=analysis_results["global_risk_level"],
                alert_msg=analysis_results["global_alert_msg"],
                camera_occluded=analysis_results["camera_occluded"],
                objects=proto_objects
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"[gRPC] Loi khi phan tich frame {request.frame_id}: {e}")
            return adas_pb2.VehicleResponse(
                frame_id=request.frame_id,
                timestamp=request.timestamp,
                risk_level="safe",
                alert_msg=f"Lỗi phân tích: {str(e)}",
                camera_occluded=False
            )

def serve_grpc():
    global grpc_server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    adas_pb2_grpc.add_VehicleAnalysisServiceServicer_to_server(VehicleAnalysisServicer(), server)
    server.add_insecure_port('0.0.0.0:50053')
    logger.info("Khoi chay gRPC Server cua Vehicle-Service tren cong 50053...")
    server.start()
    grpc_server = server
    server.wait_for_termination()

@app.on_event("startup")
def startup_event():
    service_state["running"] = True
    init_ai_core()
    # Khởi chạy gRPC server trong luồng phụ
    grpc_thread = threading.Thread(target=serve_grpc, daemon=True)
    grpc_thread.start()

@app.on_event("shutdown")
def shutdown_event():
    global grpc_server
    service_state["running"] = False
    if grpc_server:
        logger.info("Dang dung gRPC Server...")
        grpc_server.stop(0)

@app.get("/health")
def health():
    return {
        "status": "ok", 
        "service": "vehicle-service",
        "running": service_state["running"],
        "current_risk": service_state["current_risk"],
        "grpc_port": 50053
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8004"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
