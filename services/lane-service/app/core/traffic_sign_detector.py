"""
traffic_sign_detector.py

Sử dụng mô hình YOLOv11 chuyên dụng để phát hiện và nhận diện biển báo giao thông trong frame.
Chạy trực tiếp trên GPU (CUDA) nếu phần cứng hỗ trợ.
"""

import os
from ultralytics import YOLO

try:
    import torch
    AUTO_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    AUTO_DEVICE = "cpu"

try:
    from config import settings
    DEFAULT_MODEL_PATH = settings.TRAFFIC_SIGN_MODEL_PATH
    DEFAULT_CONF_THRESHOLD = settings.TRAFFIC_SIGN_CONF_THRESHOLD
except ImportError:
    DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "traffic-sign-yolo11n-classes_en.pt")
    DEFAULT_CONF_THRESHOLD = 0.45


class TrafficSignDetector:
    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        confidence_threshold: float = DEFAULT_CONF_THRESHOLD,
        device: str = AUTO_DEVICE,
    ):
        """
        Khởi tạo detector phát hiện biển báo giao thông.
        
        model_path: Đường dẫn tuyệt đối tới file trọng số .pt của model biển báo.
        confidence_threshold: Ngưỡng tin cậy tối thiểu.
        device: 'cuda' hoặc 'cpu' (mặc định tự nhận cuda nếu khả dụng).
        """
        print(f"[TrafficSignDetector] Dang tai model tu: {model_path} tren thiet bi: {device}")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Khong tim thay file model bien bao tai: {model_path}")
            
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        
        # In danh sách các nhãn nhận diện được để debug
        print(f"[TrafficSignDetector] Model load thanh cong. Danh sach nhan: {list(self.model.names.values())[:10]}... (tong cong {len(self.model.names)} nhan)")

    def detect(self, frame) -> list[dict]:
        """
        Nhận vào 1 frame (numpy array BGR).
        Trả về danh sách các biển báo phát hiện được:
            {
                "class_id": int,
                "class_name": str,
                "confidence": float,
                "bbox": {"x1": float, "y1": float, "x2": float, "y2": float}
            }
        """
        results = self.model.predict(
            source=frame,
            conf=self.confidence_threshold,
            device=self.device,
            verbose=False,
        )

        detections: list[dict] = []

        if not results:
            return detections

        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            return detections

        # Lấy bản đồ tên nhãn của model
        names_dict = self.model.names

        for box in boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            
            class_name = names_dict.get(class_id, "unknown_sign")

            detections.append({
                "class_id": class_id,
                "class_name": class_name,
                "confidence": round(confidence, 3),
                "bbox": {
                    "x1": round(x1, 1),
                    "y1": round(y1, 1),
                    "x2": round(x2, 1),
                    "y2": round(y2, 1),
                },
            })

        return detections
