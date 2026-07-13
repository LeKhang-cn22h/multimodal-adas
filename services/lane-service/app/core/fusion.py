import cv2
import numpy as np

class DataFusion:
    """
    Hợp nhất dữ liệu cảm biến: Loại trừ vùng vật cản phát hiện bởi YOLOv11
    ra khỏi mặt nạ mặt đường chạy được (Drivable Area) của DeepLabV3+.
    """
    def __init__(self):
        pass

    def fuse(self, drivable_area_mask: np.ndarray, detections: list[dict]) -> np.ndarray:
        """
        Loại bỏ các bounding box của YOLO ra khỏi drivable area.
        """
        clean_mask = drivable_area_mask.copy()
        
        for det in detections:
            bbox = det["bbox"]
            x1, y1, x2, y2 = int(bbox["x1"]), int(bbox["y1"]), int(bbox["x2"]), int(bbox["y2"])
            
            # Vẽ hình chữ nhật màu đen (0) để loại trừ vùng xe phía trước
            # Thêm khoảng đệm padding 5 pixel ở đáy để loại bỏ chân/bánh xe triệt để
            y2_padded = min(clean_mask.shape[0], y2 + 5)
            cv2.rectangle(clean_mask, (x1, y1), (x2, y2_padded), 0, -1)
            
        return clean_mask
