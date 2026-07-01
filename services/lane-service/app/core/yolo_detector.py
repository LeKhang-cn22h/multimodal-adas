"""
yolo_detector.py

Su dung YOLOv11 (ultralytics) de phat hien phuong tien / vat can trong frame.

Giai doan hien tai: dung pretrained weight COCO (yolo11n.pt), CHUA fine-tune
bang du lieu Viet Nam. Do chinh xac se duoc cai thien sau khi co Custom VN
Dataset (xem README.md muc 4 - Giai doan 2).

Model se tu dong tai ve (~5-6MB cho yolo11n.pt) tu Ultralytics vao lan chay
dau tien va cache lai, khong can tai thu cong.
"""

from ultralytics import YOLO


# Cac class lien quan toi giao thong trong bo COCO (80 class mac dinh)
COCO_VEHICLE_CLASSES = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


try:
    import torch
    AUTO_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    AUTO_DEVICE = "cpu"

try:
    from config import settings
    DEFAULT_MODEL_PATH = settings.YOLO_MODEL_PATH
    DEFAULT_CONF_THRESHOLD = settings.CONFIDENCE_THRESHOLD
except ImportError:
    DEFAULT_MODEL_PATH = "yolo11n.pt"
    DEFAULT_CONF_THRESHOLD = 0.35


class YOLODetector:
    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        confidence_threshold: float = DEFAULT_CONF_THRESHOLD,
        device: str = AUTO_DEVICE,
    ):
        """
        model_path: duong dan hoac ten weight. Mac dinh lay tu settings.
        confidence_threshold: nguong tin cay toi thieu de giu lai detection.
        device: tu dong nhan dang cuda/cpu neu de None/Default.
        """
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device

    def detect(self, frame) -> list[dict]:
        """
        Nhan vao 1 frame (numpy array, BGR - dung format OpenCV doc duoc).
        Tra ve danh sach detection, moi detection la 1 dict:
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
            classes=list(COCO_VEHICLE_CLASSES.keys()),
            device=self.device,
            verbose=False,
        )

        detections: list[dict] = []

        if not results:
            return detections

        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            return detections

        for box in boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]

            detections.append({
                "class_id": class_id,
                "class_name": COCO_VEHICLE_CLASSES.get(class_id, "unknown"),
                "confidence": round(confidence, 3),
                "bbox": {
                    "x1": round(x1, 1),
                    "y1": round(y1, 1),
                    "x2": round(x2, 1),
                    "y2": round(y2, 1),
                },
            })

        return detections