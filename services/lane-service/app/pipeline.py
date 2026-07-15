import cv2
import numpy as np
import os
import sys
import time
import grpc
import threading

# Ensure app/protos is in path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROTOS_DIR = os.path.join(APP_DIR, "protos")
if PROTOS_DIR not in sys.path:
    sys.path.insert(0, PROTOS_DIR)

import adas_pb2
import adas_pb2_grpc
from core.yolo_detector import YOLODetector
from core.deeplab_segmenter import DeepLabSegmenter
from core.geometry import LaneGeometry
from core.fusion import DataFusion
from event_client import EventClient


class LanePipeline:
    """
    Pipeline hợp nhất xử lý ADAS:
      1. Nhận diện vật cản và làn đường (tuân thủ cấu hình bật/tắt)
      2. Truyền ảnh sang vehicle-service qua gRPC để phân tích khoảng cách và nguy cơ va chạm
      3. Loại bỏ vật cản khỏi làn đường trống (Fusion)
      4. Tính toán hình học lệch tâm xe (Geometry & Lane Offset)
      5. Gửi cảnh báo lệch làn sang Aggregator (EventClient)
    """

    def __init__(self, yolo_detector: YOLODetector = None):
        self.yolo_detector = yolo_detector or YOLODetector()
        self.deeplab = DeepLabSegmenter()
        self.geometry = LaneGeometry()
        self.fusion = DataFusion()
        self.event_client = EventClient()
        
        # Cấu hình bật/tắt động mặc định
        self.config = {
            "lane_detection": True,
            "deeplab_segmentation": True,
            "vehicle_detection": True
        }
        
        # Biến đếm frame và bộ đệm cache cho gRPC
        self.frame_counter = 0
        self.last_grpc_objects = []
        self.last_risk_level = "safe"
        self.last_alert_msg = ""
        self.last_camera_occluded = False
        
        # Biến quản lý Thread gọi gRPC nền (Non-blocking)
        self.is_grpc_running = False
        self.grpc_thread = None
        
        # Cấu hình kết nối gRPC đến vehicle-service
        grpc_host = os.getenv("VEHICLE_GRPC_HOST", "localhost")
        grpc_port = os.getenv("VEHICLE_GRPC_PORT", "50053")
        grpc_target = f"{grpc_host}:{grpc_port}"
        
        print(f"[gRPC Client] Khoi tao ket noi den gRPC Server tai: {grpc_target}")
        self.grpc_channel = grpc.insecure_channel(grpc_target)
        self.vehicle_client = adas_pb2_grpc.VehicleAnalysisServiceStub(self.grpc_channel)

    def _run_grpc_request(self, jpeg_bytes, frame_id):
        self.is_grpc_running = True
        try:
            request = adas_pb2.FrameRequest(
                frame_id=frame_id,
                timestamp=time.time(),
                image_bytes=jpeg_bytes
            )
            # Tăng timeout lên 0.5s vì chạy nền không làm lag video (Non-blocking)
            response = self.vehicle_client.AnalyzeFrame(request, timeout=0.5)
            
            grpc_objects = []
            for obj in response.objects:
                grpc_objects.append({
                    "track_id": obj.track_id,
                    "class_name": obj.class_name,
                    "distance": round(obj.distance, 1),
                    "color": obj.color,
                    "bbox": list(obj.bbox)
                })
            
            self.last_grpc_objects = grpc_objects
            self.last_risk_level = response.risk_level
            self.last_alert_msg = response.alert_msg
            self.last_camera_occluded = response.camera_occluded
        except Exception as e:
            print(f"[LanePipeline] Loi goi gRPC nen (timeout/offline): {e}")
        finally:
            self.is_grpc_running = False

    def update_config(self, config_dict):
        """Cập nhật cấu hình bộ lọc từ REST API."""
        self.config.update(config_dict)
        # Bật/Tắt phân vùng DeepLab (chỉ bật nếu người dùng chọn và model thực sự đã tải trọng số thành công)
        self.deeplab.has_weights = config_dict.get("deeplab_segmentation", True) and getattr(self.deeplab, "has_weights", False)
        print(f"[LanePipeline] Cap nhat bo loc tai nguyen: {self.config}")

    def process_frame(self, frame, visualize: bool = False) -> dict:
        height, width = frame.shape[:2]

        # 1. Nhận diện Làn đường
        if self.config.get("lane_detection", True):
            # Phân vùng đường & vạch kẻ (DeepLabV3+ hoặc Fallback OpenCV nếu tắt DeepLab Seg.)
            # Tối ưu: Thu nhỏ ảnh trước khi đưa vào DeepLab để tăng FPS
            small_frame = cv2.resize(frame, (640, 360))
            drivable_mask_small, lane_mask_small = self.deeplab.segment(small_frame)
            
            # Phóng to kết quả lên bằng kích thước ban đầu (dùng INTER_NEAREST giữ nguyên giá trị 0/255)
            drivable_mask = cv2.resize(drivable_mask_small, (width, height), interpolation=cv2.INTER_NEAREST)
            lane_mask = cv2.resize(lane_mask_small, (width, height), interpolation=cv2.INTER_NEAREST)
            
            lane_info = self.geometry.analyze_lane(lane_mask)
        else:
            drivable_mask = np.zeros((height, width), dtype=np.uint8)
            lane_mask = np.zeros((height, width), dtype=np.uint8)
            lane_info = {
                "lane_detected": False,
                "lane_offset": None,
                "direction": "UNKNOWN",
                "left_line": None,
                "right_line": None
            }

        # 2. Nhận diện phương tiện & đo khoảng cách qua gRPC (gọi vehicle-service)
        grpc_objects = []
        global_risk_level = "safe"
        global_alert_msg = ""
        camera_occluded = False

        self.frame_counter += 1
        
        # Chạy gRPC 3 frame một lần (giảm 66% tải suy luận) hoặc nếu chưa có dữ liệu cache
        if not self.config.get("vehicle_detection", True):
            self.last_grpc_objects = []
            self.last_risk_level = "safe"
            self.last_alert_msg = ""
            self.last_camera_occluded = False
        else:
            # Chỉ bắn gRPC nền nếu thread cũ đã xử lý xong và đã đến chu kỳ 3 frames
            if not self.is_grpc_running and (self.frame_counter % 3 == 0 or not self.last_grpc_objects):
                # Nén ảnh thành JPEG (Giảm chất lượng xuống 65 để truyền siêu tốc)
                success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                if success:
                    jpeg_bytes = buffer.tobytes()
                    self.grpc_thread = threading.Thread(
                        target=self._run_grpc_request, 
                        args=(jpeg_bytes, self.frame_counter)
                    )
                    self.grpc_thread.daemon = True
                    self.grpc_thread.start()

            # Luôn dùng dữ liệu cache mới nhất (phiên bản bất đồng bộ)
            grpc_objects = self.last_grpc_objects
            global_risk_level = self.last_risk_level
            global_alert_msg = self.last_alert_msg
            camera_occluded = self.last_camera_occluded

        # 3. Định dạng dữ liệu tương thích ngược cho DataFusion
        detections = []
        for obj in grpc_objects:
            x1, y1, x2, y2 = obj["bbox"]
            detections.append({
                "class_name": obj["class_name"],
                "confidence": 1.0,
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            })

        # Hợp nhất dữ liệu (Fusion)
        fused_drivable = self.fusion.fuse(drivable_mask, detections)

        # 4. Gửi cảnh báo nếu xe chệch làn đường (EventClient)
        if lane_info["lane_detected"] and lane_info["direction"] in ["LEFT", "RIGHT"]:
            self.event_client.send_departure_warning(
                lane_offset=lane_info["lane_offset"],
                direction=lane_info["direction"]
            )

        # 5. Vẽ trực quan hóa lên luồng phát livestream / video output
        if visualize:
            # Vẽ vùng di chuyển được sạch (màu xanh lá)
            overlay = frame.copy()
            overlay[fused_drivable == 255] = [0, 255, 0]
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

            # Vẽ vạch kẻ đường biên trái (màu xanh dương) và biên phải (màu đỏ)
            if self.config.get("lane_detection", True):
                left_line = lane_info.get("left_line")
                right_line = lane_info.get("right_line")
                if left_line:
                    cv2.line(frame, left_line[0], left_line[1], (255, 0, 0), 3, cv2.LINE_AA)
                if right_line:
                    cv2.line(frame, right_line[0], right_line[1], (0, 0, 255), 3, cv2.LINE_AA)

            # Vẽ bounding boxes và khoảng cách của phương tiện từ gRPC
            for obj in grpc_objects:
                x1, y1, x2, y2 = [int(v) for v in obj["bbox"]]
                
                # Màu hộp bao: xanh lá (safe), cam (warning), đỏ (dangerous)
                rgb_color = (0, 255, 0)
                if obj["color"] == "orange":
                    rgb_color = (0, 165, 255)
                elif obj["color"] == "red":
                    rgb_color = (0, 0, 255)
                
                label = f"{obj['class_name']} #{obj['track_id']}: {obj['distance']}m"
                cv2.rectangle(frame, (x1, y1), (x2, y2), rgb_color, 2)
                
                (w_lbl, h_lbl), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1 - h_lbl - 5), (x1 + w_lbl, y1), rgb_color, -1)
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

            # Vẽ HUD thông số trên màn hình giám sát
            hud_bg = frame.copy()
            cv2.rectangle(hud_bg, (10, 10), (350, 80), (0, 0, 0), -1)
            cv2.addWeighted(hud_bg, 0.6, frame, 0.4, 0, frame)

            offset_val = lane_info.get("lane_offset")
            direction_val = lane_info.get("direction")
            
            if offset_val is not None:
                hud_text = f"LANE OFFSET: {offset_val}m ({direction_val})"
                text_color = (0, 0, 255) if direction_val in ["LEFT", "RIGHT"] else (0, 255, 0)
            else:
                hud_text = "LANE: UNKNOWN"
                text_color = (255, 255, 255)
            cv2.putText(frame, hud_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2, cv2.LINE_AA)
            
            # Hiển thị mức độ nguy hiểm từ vehicle-service
            risk_text = f"RISK LEVEL: {global_risk_level.upper()}"
            risk_color = (0, 255, 0)
            if global_risk_level == "low":
                risk_color = (0, 255, 255)
            elif global_risk_level in ["high", "critical"]:
                risk_color = (0, 0, 255)
            cv2.putText(frame, risk_text, (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, risk_color, 2, cv2.LINE_AA)

        return {
            "frame_width": width,
            "frame_height": height,
            "detections": detections,
            "num_detections": len(detections),
            "lane_detected": lane_info["lane_detected"],
            "lane_offset": lane_info["lane_offset"],
            "direction": lane_info["direction"],
            "global_risk_level": global_risk_level,
            "global_alert_msg": global_alert_msg,
            "camera_occluded": camera_occluded,
            "objects": grpc_objects,
            "message": "gRPC Lane-Vehicle Pipeline active.",
        }