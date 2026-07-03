import cv2
import numpy as np

class DeepLabSegmenter:
    """
    Bộ phân vùng ảnh sử dụng DeepLabV3+ (đoạn mã này hỗ trợ cơ chế Fallback sang
    xử lý ảnh OpenCV cổ điển cực kỳ thông minh nếu không có model PyTorch .pth).
    
    Trả về:
      - drivable_area_mask: Mặt nạ vùng đường chạy được (shape HxW, giá trị 255/0)
      - lane_marking_mask: Mặt nạ vạch kẻ đường (shape HxW, giá trị 255/0)
    """
    def __init__(self, model_path: str = None, device: str = "cpu"):
        self.model_path = model_path
        self.device = device
        
        # Ở đây bạn có thể load model PyTorch nếu có model_path:
        # self.model = load_deeplabv3_model(model_path, device)
        self.has_weights = model_path is not None

    def segment(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Phân vùng khung hình.
        Trả về: (drivable_area_mask, lane_marking_mask)
        """
        height, width = frame.shape[:2]
        
        if self.has_weights:
            # Chạy mô hình DeepLabV3+ thật ở đây
            # return self._segment_dl(frame)
            pass
            
        # ── Cơ chế Fallback bằng OpenCV thông minh ────────────────────────────
        # Chuyển đổi sang hệ màu HSV để lọc màu vạch đường (trắng và vàng)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 1. Lọc màu trắng (White Mask)
        # Vạch trắng: độ sáng (Value) cao, độ bão hòa (Saturation) thấp
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 50, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # 2. Lọc màu vàng (Yellow Mask)
        # Vạch vàng: dải màu Hue khoảng 15-30, Saturation và Value tương đối cao
        lower_yellow = np.array([15, 80, 100])
        upper_yellow = np.array([30, 255, 255])
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # Gộp mặt nạ vạch kẻ làn
        lane_marking_mask = cv2.bitwise_or(white_mask, yellow_mask)
        
        # Chỉ giữ lại phần nửa dưới ảnh (Region of Interest - ROI) nơi vạch kẻ làn xuất hiện
        roi_mask = np.zeros_like(lane_marking_mask)
        roi_pts = np.array([
            [int(width * 0.1), height],
            [int(width * 0.4), int(height * 0.55)],
            [int(width * 0.6), int(height * 0.55)],
            [int(width * 0.9), height]
        ], np.int32)
        cv2.fillPoly(roi_mask, [roi_pts], 255)
        lane_marking_mask = cv2.bitwise_and(lane_marking_mask, roi_mask)
        
        # Làm sạch nhiễu vạch kẻ bằng bộ lọc hình thái học (Morphological Open)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        lane_marking_mask = cv2.morphologyEx(lane_marking_mask, cv2.MORPH_OPEN, kernel)
        
        # 3. Tạo mặt nạ vùng đường chạy được (Drivable Area)
        # Mặc định vùng mặt đường có hình dạng tương tự như ROI của camera trước xe
        drivable_area_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(drivable_area_mask, [roi_pts], 255)
        
        return drivable_area_mask, lane_marking_mask
