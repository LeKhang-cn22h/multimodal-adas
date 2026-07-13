import cv2
import numpy as np


class DeepLabSegmenter:
    """
    Bộ phân vùng ảnh kết hợp:
      - Lọc màu HSV (trắng + vàng) — phát hiện vạch kẻ theo màu
      - Canny Edge Detection trên Grayscale + Dilation — phát hiện viền vạch sắc nét
      (Fallback thông minh khi chưa có model DeepLabV3+ .pth thật)

    Cải tiến từ 3 file tham khảo:
      - Thêm pipeline Grayscale → Dilation → Canny bên cạnh HSV filter
      - Kết hợp (OR) hai mask để tăng recall phát hiện vạch kẻ
      - Giữ nguyên ROI và morphological cleanup

    Trả về:
      - drivable_area_mask: Mặt nạ vùng đường chạy được (HxW, giá trị 0/255)
      - lane_marking_mask:  Mặt nạ vạch kẻ đường    (HxW, giá trị 0/255)
    """

    def __init__(self, model_path: str = None, device: str = "cpu"):
        # model_path để dành tích hợp model DeepLabV3+ thật sau này
        self.model_path = model_path
        self.device = device
        self._morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        self._dilation_kernel = np.ones((3, 3), np.uint8)

    def segment(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Phân vùng khung hình.

        Args:
            frame: Ảnh BGR từ OpenCV.

        Returns:
            (drivable_area_mask, lane_marking_mask) — cả hai shape (H, W), dtype uint8.
        """
        height, width = frame.shape[:2]

        # ── Xây dựng ROI (hình thang nhìn về phía trước xe) ─────────────────
        roi_pts = np.array([
            [int(width * 0.10), height],
            [int(width * 0.40), int(height * 0.52)],
            [int(width * 0.60), int(height * 0.52)],
            [int(width * 0.90), height],
        ], np.int32)

        roi_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(roi_mask, [roi_pts], 255)

        # ── Nhánh 1: Lọc màu HSV (trắng + vàng) ─────────────────────────────
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Vạch trắng: Value cao, Saturation thấp
        white_mask = cv2.inRange(hsv,
                                  np.array([0,   0,   190]),
                                  np.array([180, 55,  255]))

        # Vạch vàng: Hue ~15-35, Saturation và Value tương đối cao
        yellow_mask = cv2.inRange(hsv,
                                   np.array([15,  80, 100]),
                                   np.array([35, 255, 255]))

        hsv_mask = cv2.bitwise_or(white_mask, yellow_mask)

        # ── Nhánh 2: Canny Edge Detection (kỹ thuật từ 3 file tham khảo) ─────
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dilated = cv2.dilate(gray, kernel=self._dilation_kernel)
        canny_mask = cv2.Canny(dilated, 60, 200)

        # Lọc bỏ Canny nằm ngoài vùng màu vàng/trắng (giảm nhiễu từ vật thể khác)
        # Chỉ giữ pixel Canny nằm gần vùng HSV để tránh nhận nhầm xe/bầu trời
        dilated_hsv = cv2.dilate(hsv_mask, np.ones((7, 7), np.uint8))
        canny_filtered = cv2.bitwise_and(canny_mask, dilated_hsv)

        # ── Kết hợp 2 mask ───────────────────────────────────────────────────
        combined = cv2.bitwise_or(hsv_mask, canny_filtered)

        # Cắt theo ROI
        lane_marking_mask = cv2.bitwise_and(combined, roi_mask)

        # Morphological cleanup: loại bỏ nhiễu nhỏ (Opening)
        lane_marking_mask = cv2.morphologyEx(
            lane_marking_mask, cv2.MORPH_OPEN, self._morph_kernel
        )

        # ── Drivable area mask ────────────────────────────────────────────────
        drivable_area_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(drivable_area_mask, [roi_pts], 255)

        return drivable_area_mask, lane_marking_mask
