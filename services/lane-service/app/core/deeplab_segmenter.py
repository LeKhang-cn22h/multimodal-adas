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

    def __init__(self, model_path: str = "", device: str = "cpu"):
        import os
        import sys
        
        # Thiet lap cac duong dan tu dong tim file best_deeplab.pth
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_paths = [
            os.path.join(app_dir, "models", "best_deeplab.pth"),
            os.path.join(app_dir, "training", "models", "best_deeplab.pth"),
            os.path.join(os.path.dirname(app_dir), "models", "best_deeplab.pth"),
            os.path.join(os.path.dirname(app_dir), "models", "best_deeplabv3_mobilenet_voc_os16.pth"),
        ]
        
        self.model_path = model_path
        if not self.model_path:
            for path in default_paths:
                if os.path.exists(path):
                    self.model_path = path
                    print("[DEEPLAB] DA NAP MODEL TAI", self.model_path)
                    break
                    
        self.device = device
        self._morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        self._dilation_kernel = np.ones((3, 3), np.uint8)
        
        # Tu dong nap model PyTorch neu tim thay file pth
        self.has_weights = False
        if self.model_path and os.path.exists(self.model_path):
            try:
                import torch
                # Import get_model
                sys.path.append(os.path.join(app_dir, "training"))
                from model import get_model
                
                self.device_torch = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                self.model = get_model(num_classes=3)
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device_torch, weights_only=False))
                self.model.to(self.device_torch)
                self.model.eval()
                self.has_weights = True
                print(f"[DeepLabSegmenter] Successfully loaded trained weights from {self.model_path}")
            except Exception as e:
                print(f"[DeepLabSegmenter] Failed to load trained weights, falling back to OpenCV. Error: {e}")

    def segment(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Phân vùng khung hình.
        """
        height, width = frame.shape[:2]

        if self.has_weights:
            try:
                import torch
                import torchvision.transforms as T
                
                # Chuyen doi va resize anh de dua vao model PyTorch
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_resized = cv2.resize(img_rgb, (640, 360))
                
                transform = T.Compose([
                    T.ToTensor(),
                    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                ])
                img_tensor = transform(img_resized).unsqueeze(0).to(self.device_torch)
                
                with torch.no_grad():
                    output = self.model(img_tensor)['out']
                    pred = torch.argmax(output, dim=1).squeeze(0).cpu().numpy()
                
                # Resize mat na pred ve lai kich thuoc ban dau bang INTER_NEAREST
                pred_resized = cv2.resize(pred.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST)
                
                # Phuc hoi drivable area (class 1) va lane marking (class 2)
                drivable_area_mask = ((pred_resized == 1) * 255).astype(np.uint8)
                lane_marking_mask = ((pred_resized == 2) * 255).astype(np.uint8)
                
                return drivable_area_mask, lane_marking_mask
            except Exception as e:
                print(f"[DeepLabSegmenter] Error during AI inference, falling back to OpenCV. Error: {e}")


        # ── Xây dựng ROI (hình thang nhìn về phía trước xe) ─────────────────
        roi_pts = np.array([
            [int(width * 0.18), height],
            [int(width * 0.43), int(height * 0.62)],
            [int(width * 0.57), int(height * 0.62)],
            [int(width * 0.82), height],
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
