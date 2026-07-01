from core.yolo_detector import YOLODetector


class LanePipeline:
    """
    Giai doan hien tai: chi chay YOLOv11 de phat hien phuong tien / vat can.

    DeepLabV3+ (phan vung lan duong) va OpenCV geometry (tinh lane_offset)
    CHUA duoc trien khai o buoc nay - se lam o cac checkpoint tiep theo.
    """

    def __init__(self):
        self.yolo_detector = YOLODetector()

    def process_frame(self, frame) -> dict:
        height, width = frame.shape[:2]

        detections = self.yolo_detector.detect(frame)

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