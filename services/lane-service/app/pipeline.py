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

from core.vehicle_detector import ObjectDetector
from core.risk_analyzer import RiskAnalyzer
from core.deeplab_segmenter import DeepLabSegmenter
from core.traffic_sign_detector import TrafficSignDetector
from core.geometry import LaneGeometry
from core.fusion import DataFusion

# Import RabbitMQ messaging components
from app.messaging.connection import RabbitMQConnectionManager
from app.messaging.publisher import ResultPublisher


class LanePipeline:
    """
    Unified ADAS Pipeline processing on RAM:
      1. Performs drivable area and lane segmentation (DeepLab)
      2. Executes vehicle detection & ByteTrack tracking (YOLOv11s local)
      3. Performs distance estimation and risk analysis (RiskAnalyzer)
      4. Calculates ego-lane deviation offset and departure warning
      5. Publishes dual stream alerts (lane and vehicle) to RabbitMQ
    """

    def __init__(self, vehicle_detector: ObjectDetector = None, traffic_sign_detector: TrafficSignDetector = None) -> None:
        # Load configurations
        from config import settings
        
        # Load local modules directly on RAM
        self.vehicle_detector = vehicle_detector or ObjectDetector()
        self.risk_analyzer = RiskAnalyzer()
        self.traffic_sign_detector = traffic_sign_detector or TrafficSignDetector()
        self.deeplab = DeepLabSegmenter()
        self.geometry = LaneGeometry()
        self.fusion = DataFusion()
        
        # Dynamic filter toggles
        self.config = {
            "lane_detection": True,
            "deeplab_segmentation": True,
            "vehicle_detection": True,
            "traffic_sign_detection": True
        }
        
        # Frame counter and cache parameters
        self.frame_counter = 0
        self.last_grpc_objects = []
        self.last_risk_level = "safe"
        self.last_alert_msg = ""
        self.last_camera_occluded = False
        
        # State machine for RabbitMQ lane alert stream
        self._lane_is_warning = False
        self._lane_last_warning_time = 0.0
        self._lane_last_payload = None
        self._lane_last_publish_time = 0.0
        
        # State machine for RabbitMQ vehicle alert stream
        self._vehicle_is_warning = False
        self._vehicle_last_warning_time = 0.0
        self._vehicle_last_payload = None
        self._vehicle_last_publish_time = 0.0
        
        self._safe_cooldown_seconds = settings.SAFE_COOLDOWN_SECONDS
        
        # Initialize RabbitMQ ResultPublisher in a background thread to prevent blocking main application startup
        rabbitmq_host = settings.RABBITMQ_HOST
        rabbitmq_port = settings.RABBITMQ_PORT
        rabbitmq_user = settings.RABBITMQ_USER
        rabbitmq_pass = settings.RABBITMQ_PASS
        
        self._publisher = None
        
        def init_rabbitmq():
            print(f"[RabbitMQ Client] Initializing publisher to: {rabbitmq_host}:{rabbitmq_port} in background")
            try:
                self._mq_manager = RabbitMQConnectionManager(
                    host=rabbitmq_host,
                    port=rabbitmq_port,
                    username=rabbitmq_user,
                    password=rabbitmq_pass
                )
                self._mq_manager.connect()
                self._publisher = ResultPublisher(self._mq_manager)
                self._publisher.start()
                print("[RabbitMQ Client] Publisher started successfully")
            except Exception as exc:
                print(f"[RabbitMQ Client] Connection failed: {exc}")
                self._publisher = None

        import threading
        threading.Thread(target=init_rabbitmq, daemon=True).start()

    @property
    def is_mq_connected(self) -> bool:
        if hasattr(self, "_mq_manager") and self._mq_manager is not None:
            return self._mq_manager.is_connected
        return False

    def update_config(self, config_dict):
        """Cập nhật cấu hình bộ lọc từ REST API."""
        self.config.update(config_dict)
        # Bật/Tắt phân vùng DeepLab (chỉ bật nếu người dùng chọn và model thực sự đã tải trọng số thành công)
        self.deeplab.has_weights = config_dict.get("deeplab_segmentation", True) and getattr(self.deeplab, "has_weights", False)
        print(f"[LanePipeline] Cap nhat bo loc tai nguyen: {self.config}")

    def process_frame(self, frame, visualize: bool = False) -> dict:
        height, width = frame.shape[:2]

        # 1. Lane detection
        if self.config.get("lane_detection", True):
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

        # 2. Local Vehicle detection & Distance estimation on RAM
        self.frame_counter += 1
        
        if not self.config.get("vehicle_detection", True):
            self.last_grpc_objects = []
            self.last_risk_level = "safe"
            self.last_alert_msg = ""
            self.last_camera_occluded = False
        else:
            # Run YOLOv11 local tracking
            track_result = self.vehicle_detector.track_objects(frame)
            
            boxes = track_result.boxes.xyxy.cpu().numpy() if track_result.boxes is not None else []
            class_ids = track_result.boxes.cls.cpu().numpy() if track_result.boxes is not None else []
            track_ids = track_result.boxes.id.cpu().numpy() if (track_result.boxes is not None and track_result.boxes.id is not None) else [-1] * len(boxes)
            confidences = track_result.boxes.conf.cpu().numpy() if track_result.boxes is not None else []
            
            # Apply geometric filters
            keep_indices = self.vehicle_detector.filter_inside_vehicles(boxes, class_ids, track_ids)
            keep_indices = [idx for idx in keep_indices if idx in self.vehicle_detector.filter_outside_lane(boxes, class_ids, track_ids, height, width)]
            
            filtered_boxes = [boxes[idx] for idx in keep_indices]
            filtered_class_ids = [class_ids[idx] for idx in keep_indices]
            filtered_track_ids = [track_ids[idx] for idx in keep_indices]
            filtered_confidences = [confidences[idx] for idx in keep_indices]
            
            # Run local risk analyzer
            risk_res = self.risk_analyzer.analyze_frame(
                frame=frame,
                boxes=filtered_boxes,
                class_ids=filtered_class_ids,
                track_ids=filtered_track_ids,
                confidences=filtered_confidences,
                frame_id=self.frame_counter
            )
            
            self.last_grpc_objects = risk_res["objects"]
            self.last_risk_level = risk_res["global_risk_level"]
            self.last_alert_msg = risk_res["global_alert_msg"]
            self.last_camera_occluded = risk_res["camera_occluded"]

        grpc_objects = self.last_grpc_objects
        global_risk_level = self.last_risk_level
        global_alert_msg = self.last_alert_msg
        camera_occluded = self.last_camera_occluded

        # 2.5 Phát hiện biển báo giao thông
        traffic_signs = []
        if self.config.get("traffic_sign_detection", True):
            try:
                traffic_signs = self.traffic_sign_detector.detect(frame)
            except Exception as e:
                print(f"[LanePipeline] Loi khi detect bien bao: {e}")

        # 3. Format detections for DataFusion
        detections = []
        for obj in grpc_objects:
            x1, y1, x2, y2 = obj["bbox"]
            detections.append({
                "class_name": obj["class_name"],
                "confidence": 1.0,
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            })

        # Data fusion: subtract obstacles from drivable area
        fused_drivable = self.fusion.fuse(drivable_mask, detections)

        # 4. RabbitMQ state machine with cooldown logic
        import time
        if self._publisher is not None:
            # ── Stream 1: Lane Safety ──────────────────────────────
            lane_has_anomaly = lane_info["lane_detected"] and (lane_info["direction"] in ["LEFT", "RIGHT"])
            msg_lane = "Xe dang di dung lan duong."
            weight_lane = 0.0
            
            if lane_has_anomaly:
                offset_val = lane_info["lane_offset"]
                dir_str = "trai" if lane_info["direction"] == "LEFT" else "phai"
                msg_lane = f"Canh bao: Xe lech lan ve ben {dir_str} (offset: {offset_val}m)!"
                weight_lane = float(abs(offset_val)) if offset_val is not None else 1.0
                
            if lane_has_anomaly:
                self._lane_last_warning_time = time.time()
                payload_lane = {
                    "from": "lane-service",
                    "message": msg_lane,
                    "weight": weight_lane
                }
                self._lane_last_payload = payload_lane
                if time.time() - self._lane_last_publish_time >= 2.0:
                    self._publisher.publish(payload_lane)
                    self._lane_last_publish_time = time.time()
                self._lane_is_warning = True
            else:
                if self._lane_is_warning:
                    elapsed = time.time() - self._lane_last_warning_time
                    if elapsed < self._safe_cooldown_seconds:
                        if self._lane_last_payload:
                            if time.time() - self._lane_last_publish_time >= 2.0:
                                self._publisher.publish(self._lane_last_payload)
                                self._lane_last_publish_time = time.time()
                    else:
                        safe_lane = {
                            "from": "lane-service",
                            "message": "Xe dang di dung lan duong.",
                            "weight": 0.0
                        }
                        self._publisher.publish(safe_lane)
                        self._lane_last_publish_time = time.time()
                        self._lane_last_payload = None
                        self._lane_is_warning = False

            # ── Stream 2: Collision Safety (Vehicle) ───────────────
            vehicle_has_anomaly = global_risk_level in ["high", "critical"]
            msg_vehicle = "Khoang cach phia truoc an toan."
            weight_vehicle = 0.0
            
            if vehicle_has_anomaly:
                msg_vehicle = global_alert_msg or "Phuong tien phia truoc qua gan!"
                weight_vehicle = 2.0 if global_risk_level == "critical" else 1.0
                
            if vehicle_has_anomaly:
                self._vehicle_last_warning_time = time.time()
                payload_vehicle = {
                    "from": "vehicle-service",
                    "message": msg_vehicle,
                    "weight": weight_vehicle
                }
                self._vehicle_last_payload = payload_vehicle
                if time.time() - self._vehicle_last_publish_time >= 2.0:
                    self._publisher.publish(payload_vehicle)
                    self._vehicle_last_publish_time = time.time()
                self._vehicle_is_warning = True
            else:
                if self._vehicle_is_warning:
                    elapsed = time.time() - self._vehicle_last_warning_time
                    if elapsed < self._safe_cooldown_seconds:
                        if self._vehicle_last_payload:
                            if time.time() - self._vehicle_last_publish_time >= 2.0:
                                self._publisher.publish(self._vehicle_last_payload)
                                self._vehicle_last_publish_time = time.time()
                    else:
                        safe_vehicle = {
                            "from": "vehicle-service",
                            "message": "Khoang cach phia truoc an toan.",
                            "weight": 0.0
                        }
                        self._publisher.publish(safe_vehicle)
                        self._vehicle_last_publish_time = time.time()
                        self._vehicle_last_payload = None
                        self._vehicle_is_warning = False



        # 5. Vẽ trực quan hóa lên luồng phát livestream / video output
        if visualize:
            # Vẽ vùng di chuyển được sạch (màu xanh lá)
            overlay = frame.copy()
            overlay[fused_drivable == 255] = [0, 255, 0]
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

            # Vẽ vạch kẻ đường biên trái (màu xanh dương) và biên phải (màu đỏ) dưới dạng đường cong mượt mà
            if self.config.get("lane_detection", True) and lane_info.get("lane_detected", False):
                left_fitx = lane_info.get("left_fitx")
                right_fitx = lane_info.get("right_fitx")
                ploty = lane_info.get("ploty")
                
                if left_fitx is not None and right_fitx is not None and ploty is not None:
                    # Lấy vùng vẽ khớp chính xác với ROI (từ 62% chiều cao ảnh xuống)
                    y_start = int(height * 0.62)
                    mask_y = ploty >= y_start
                    ploty_clip = ploty[mask_y]
                    left_clip = left_fitx[mask_y]
                    right_clip = right_fitx[mask_y]
                    
                    pts_l = []
                    pts_r = []
                    # Duyệt qua các điểm để warp ngược về ảnh gốc
                    for y_val, lx, rx in zip(ploty_clip, left_clip, right_clip):
                        pt_l = self.geometry._warp_point_inv((int(lx), int(y_val)), (width, height))
                        pt_r = self.geometry._warp_point_inv((int(rx), int(y_val)), (width, height))
                        if pt_l:
                            pts_l.append(pt_l)
                        if pt_r:
                            pts_r.append(pt_r)
                            
                    if len(pts_l) > 1:
                        pts_l = np.array(pts_l, dtype=np.int32)
                        cv2.polylines(frame, [pts_l], False, (255, 0, 0), 3, cv2.LINE_AA) # Blue
                    if len(pts_r) > 1:
                        pts_r = np.array(pts_r, dtype=np.int32)
                        cv2.polylines(frame, [pts_r], False, (0, 0, 255), 3, cv2.LINE_AA) # Red

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

            # Vẽ bounding boxes cho biển báo giao thông phát hiện được
            for sign in traffic_signs:
                sx1, sy1, sx2, sy2 = [int(v) for v in [sign["bbox"]["x1"], sign["bbox"]["y1"], sign["bbox"]["x2"], sign["bbox"]["y2"]]]
                sign_color = (255, 0, 255)  # Màu tím sáng (Magenta)
                sign_label = f"{sign['class_name']} ({int(sign['confidence']*100)}%)"
                cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), sign_color, 2)
                (sw_lbl, sh_lbl), _ = cv2.getTextSize(sign_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(frame, (sx1, sy1 - sh_lbl - 5), (sx1 + sw_lbl, sy1), sign_color, -1)
                cv2.putText(frame, sign_label, (sx1, sy1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

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
            "traffic_signs": traffic_signs,
            "num_traffic_signs": len(traffic_signs),
            "message": "gRPC Lane-Vehicle Pipeline active.",
        }