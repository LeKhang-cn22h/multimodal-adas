import cv2
import numpy as np
from core.yolo_detector import YOLODetector
from core.deeplab_segmenter import DeepLabSegmenter
from core.geometry import LaneGeometry
from core.fusion import DataFusion
from event_client import EventClient


class LanePipeline:
    """
    Pipeline hợp nhất xử lý ADAS:
      1. Nhận diện vật cản (YOLOv11)
      2. Phân vùng mặt đường và làn đường (DeepLabV3+)
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

    def process_frame(self, frame, visualize: bool = False) -> dict:
        height, width = frame.shape[:2]

        # 1. Nhận diện vật cản (YOLO)
        detections = self.yolo_detector.detect(frame)

        # 2. Phân vùng đường & vạch kẻ (DeepLabV3+)
        drivable_mask, lane_mask = self.deeplab.segment(frame)

        # 3. Hợp nhất dữ liệu (Fusion)
        fused_drivable = self.fusion.fuse(drivable_mask, detections)

        # 4. Phân tích hình học đường làn (Geometry)
        lane_info = self.geometry.analyze_lane(lane_mask)

        # 5. Gửi cảnh báo nếu xe chệch làn đường (EventClient)
        if lane_info["lane_detected"] and lane_info["direction"] in ["LEFT", "RIGHT"]:
            self.event_client.send_departure_warning(
                lane_offset=lane_info["lane_offset"],
                direction=lane_info["direction"]
            )

        # 6. Vẽ trực quan hóa nếu được yêu cầu (Livestream / Video output)
        if visualize:
            # 6.1 Vẽ vùng di chuyển được sạch (Fused Drivable Area) màu xanh lá bán trong suốt
            overlay = frame.copy()
            overlay[fused_drivable == 255] = [0, 255, 0]
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

            # 6.2 Vẽ vạch kẻ đường biên trái (màu xanh dương) và biên phải (màu đỏ)
            left_line = lane_info.get("left_line")
            right_line = lane_info.get("right_line")
            if left_line:
                cv2.line(frame, left_line[0], left_line[1], (255, 0, 0), 3, cv2.LINE_AA)
            if right_line:
                cv2.line(frame, right_line[0], right_line[1], (0, 0, 255), 3, cv2.LINE_AA)

            # 6.3 Vẽ YOLO boxes các phương tiện
            for det in detections:
                bbox = det["bbox"]
                x1, y1, x2, y2 = int(bbox["x1"]), int(bbox["y1"]), int(bbox["x2"]), int(bbox["y2"])
                label = f"{det['class_name']} {det['confidence']:.2f}"
                
                # Vẽ hộp màu đỏ
                color = (0, 0, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Vẽ nhãn chữ
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1 - h - 5), (x1 + w, y1), color, -1)
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

            # 6.4 Vẽ hiển thị thông số HUD lái xe (Offset & Direction) góc trên bên trái
            offset_val = lane_info.get("lane_offset")
            direction_val = lane_info.get("direction")
            
            hud_bg = frame.copy()
            cv2.rectangle(hud_bg, (10, 10), (320, 60), (0, 0, 0), -1)
            cv2.addWeighted(hud_bg, 0.6, frame, 0.4, 0, frame)
            
            if offset_val is not None:
                hud_text = f"LANE OFFSET: {offset_val}m ({direction_val})"
                # Đổi màu chữ cảnh báo nếu chệch làn
                text_color = (0, 0, 255) if direction_val in ["LEFT", "RIGHT"] else (0, 255, 0)
            else:
                hud_text = "LANE: UNKNOWN"
                text_color = (255, 255, 255)
                
            cv2.putText(frame, hud_text, (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2, cv2.LINE_AA)

        return {
            "frame_width": width,
            "frame_height": height,
            "detections": detections,
            "num_detections": len(detections),
            "lane_detected": lane_info["lane_detected"],
            "lane_offset": lane_info["lane_offset"],
            "direction": lane_info["direction"],
            "message": "Full ADAS pipeline (YOLO + Lane Segmentation + Geometry + Fusion) is active.",
        }