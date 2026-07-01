import cv2
import numpy as np
from core.yolo_detector import YOLODetector


class LanePipeline:
    """
    Giai doan hien tai: chi chay YOLOv11 de phat hien phuong tien / vat can.

    DeepLabV3+ (phan vung lan duong) va OpenCV geometry (tinh lane_offset)
    CHUA duoc trien khai o buoc nay - se lam o cac checkpoint tiep theo.
    """

    def __init__(self, yolo_detector: YOLODetector = None):
        self.yolo_detector = yolo_detector or YOLODetector()

    def process_frame(self, frame, visualize: bool = False) -> dict:
        height, width = frame.shape[:2]

        detections = self.yolo_detector.detect(frame)

        if visualize:
            # 1. Vẽ vùng di chuyển được giả lập (Drivable Area) bằng màu xanh lá bán trong suốt
            overlay = frame.copy()
            # Hình thang đại diện cho làn đường trước mũi xe
            pts = np.array([
                [int(width * 0.45), int(height * 0.65)],
                [int(width * 0.55), int(height * 0.65)],
                [int(width * 0.90), int(height * 1.0)],
                [int(width * 0.10), int(height * 1.0)]
            ], np.int32)
            cv2.fillPoly(overlay, [pts], (0, 255, 0))
            # Trộn ảnh (30% overlay, 70% frame gốc)
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

            # 2. Vẽ YOLO detection bounding boxes
            for det in detections:
                bbox = det["bbox"]
                x1, y1, x2, y2 = int(bbox["x1"]), int(bbox["y1"]), int(bbox["x2"]), int(bbox["y2"])
                label = f"{det['class_name']} {det['confidence']:.2f}"
                
                # Vẽ hộp màu xanh đỏ/vàng tùy loại vật cản
                color = (0, 0, 255) if det["class_name"] in ["car", "bus", "truck"] else (0, 255, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Nhãn chữ kèm nền
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1 - h - 5), (x1 + w, y1), color, -1)
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        return {
            "frame_width": width,
            "frame_height": height,
            "detections": detections,
            "num_detections": len(detections),
            "lane_detected": False,
            "lane_offset": None,
            "direction": "UNKNOWN",
            "message": "YOLOv11 detection is running. Lane segmentation (DeepLabV3+ / OpenCV) is not implemented yet.",
        }

