"""
LaneGeometry v2 - Sliding Window + Perspective Warp
=====================================================
Thuật toán nhận diện làn đường dựa trên kỹ thuật:
  1. Perspective Warp (Bird's-eye view)
  2. Sliding Window để tìm điểm vạch kẻ
  3. Polynomial Curve Fit bậc 2 (ổn định hơn bậc 1 trên đường cong)
  4. Averaging 3 frame để giảm nhiễu
  5. Inverse Perspective Warp để vẽ overlay lên ảnh gốc
"""
import cv2
import numpy as np
from core.hud import draw_hud


class LaneGeometry:
    """
    Phân tích hình học đường làn bằng thuật toán Sliding Window + Perspective Warp.
    - Chuẩn hóa từ kỹ thuật birdseye-view giống bộ code tham khảo.
    - Khớp đa thức bậc 2 thay vì bậc 1 → xử lý tốt đường cong.
    - Averaging 10 frame liên tiếp để làm mượt đường biên.
    """

    def __init__(self, lane_width_meters: float = 3.7, n_frames_avg: int = 15):
        self.lane_width_meters = lane_width_meters

        # Tọa độ nguồn cho perspective warp (tỷ lệ / frame size)
        # Format: [TopLeft, TopRight, BottomLeft, BottomRight] (x_ratio, y_ratio)
        self.src_pts = np.float32([
            (0.44, 0.55),   # Top-left  — nâng cao để nhìn xa trên cao tốc
            (0.56, 0.55),   # Top-right — nâng cao để nhìn xa trên cao tốc
            (0.18, 1.00),   # Bottom-left — thu hẹp lại để loại bỏ làn bên cạnh và hộ lan
            (0.82, 1.00),   # Bottom-right — thu hẹp lại để loại bỏ làn bên cạnh và hộ lan
        ])
        self.dst_pts = np.float32([
            (0.00, 0.00),   # Top-left
            (1.00, 0.00),   # Top-right
            (0.00, 1.00),   # Bottom-left
            (1.00, 1.00),   # Bottom-right
        ])

        # Buffer trung bình hóa hệ số đa thức bậc 2: a, b, c cho left & right
        self._left_a:  list = []
        self._left_b:  list = []
        self._left_c:  list = []
        self._right_a: list = []
        self._right_b: list = []
        self._right_c: list = []
        self._n = n_frames_avg

    # ── Perspective Warp ────────────────────────────────────────────────────
    def _perspective_warp(self, img: np.ndarray) -> np.ndarray:
        """Biến đổi ảnh về góc nhìn bird's-eye view."""
        h, w = img.shape[:2]
        img_size = np.float32([(w, h)])
        src = self.src_pts * img_size
        dst = self.dst_pts * np.float32([(w, h)])
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(img, M, (w, h))

    def _inv_perspective_warp(self, img: np.ndarray, dst_size: tuple) -> np.ndarray:
        """Biến đổi ngược về góc nhìn camera để overlay lên ảnh gốc."""
        h, w = img.shape[:2]
        img_size = np.float32([(w, h)])
        src = self.dst_pts * img_size          # src/dst đảo ngược so với forward
        dst = self.src_pts * np.float32([(dst_size[0], dst_size[1])])
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(img, M, dst_size)

    # ── Thresholding (màu + canny) ──────────────────────────────────────────
    def _threshold(self, img: np.ndarray) -> np.ndarray:
        """
        Áp dụng lọc màu (trắng + vàng) và Canny để tạo mặt nạ nhị phân làn đường.
        Nếu đầu vào đã là mask nhị phân từ DeepLab thì trả về ngay.
        """
        # Nếu đầu vào đã là ảnh nhị phân (mask từ DeepLab)
        if len(img.shape) == 2:
            return img

        # Lọc màu vàng + trắng
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        white_mask  = cv2.inRange(hsv, np.array([0,   0, 200]), np.array([255, 45, 255]))
        yellow_mask = cv2.inRange(hsv, np.array([18,  94, 140]), np.array([48, 255, 255]))
        color_mask = cv2.bitwise_or(white_mask, yellow_mask)

        # Canny edge
        gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur  = cv2.GaussianBlur(gray, (5, 5), 0)
        canny = cv2.Canny(blur, 50, 100)
        kernel = np.ones((5, 5), np.uint8)
        canny  = cv2.dilate(canny, kernel, iterations=1)
        canny  = cv2.erode(canny, kernel, iterations=1)

        return cv2.bitwise_or(color_mask, canny)

    # ── Sliding Window ──────────────────────────────────────────────────────
    def _sliding_window(
        self,
        warped: np.ndarray,
        n_windows: int = 12,
        margin: int = 50,
        min_pix: int = 10,
    ) -> tuple:
        """
        Tìm điểm vạch kẻ trái/phải bằng cửa sổ trượt trên bird's-eye view.
        Trả về (left_fitx, right_fitx, ploty, left_fit_, right_fit_) hoặc None.
        """
        h, w = warped.shape[:2]

        # Histogram nửa dưới ảnh để tìm vị trí bắt đầu
        histogram = np.sum(warped[h // 2:, :], axis=0)
        
        # Tối ưu: Giới hạn nhẹ vùng quét để loại bỏ nhiễu sát rìa cực biên
        left_search_min = int(w * 0.02)
        left_search_max = int(w * 0.47)
        right_search_min = int(w * 0.53)
        right_search_max = int(w * 0.98)
        
        leftx_base = int(np.argmax(histogram[left_search_min:left_search_max])) + left_search_min
        rightx_base = int(np.argmax(histogram[right_search_min:right_search_max])) + right_search_min

        window_h = h // n_windows
        nonzero  = warped.nonzero()
        nzy = np.array(nonzero[0])
        nzx = np.array(nonzero[1])

        leftx_cur  = leftx_base
        rightx_cur = rightx_base
        left_inds  = []
        right_inds = []

        for win in range(n_windows):
            y_low  = h - (win + 1) * window_h
            y_high = h - win * window_h

            xl_lo = leftx_cur  - margin
            xl_hi = leftx_cur  + margin
            xr_lo = rightx_cur - margin
            xr_hi = rightx_cur + margin

            good_l = ((nzy >= y_low) & (nzy < y_high) & (nzx >= xl_lo) & (nzx < xl_hi)).nonzero()[0]
            good_r = ((nzy >= y_low) & (nzy < y_high) & (nzx >= xr_lo) & (nzx < xr_hi)).nonzero()[0]

            left_inds.append(good_l)
            right_inds.append(good_r)

            if len(good_l) > min_pix:
                leftx_cur = int(np.mean(nzx[good_l]))
            if len(good_r) > min_pix:
                rightx_cur = int(np.mean(nzx[good_r]))

        left_inds  = np.concatenate(left_inds)
        right_inds = np.concatenate(right_inds)

        leftx  = nzx[left_inds]
        lefty  = nzy[left_inds]
        rightx = nzx[right_inds]
        righty = nzy[right_inds]

        if leftx.size < 30 or rightx.size < 30:
            return None

        # Fit đa thức bậc 2: x = a*y^2 + b*y + c  (dùng y làm biến độc lập)
        lf = np.polyfit(lefty,  leftx,  2)
        rf = np.polyfit(righty, rightx, 2)

        # Kiểm tra xem đường biên trái và phải có cắt chéo nhau (lỗi hình chữ X do nhiễu vỉa hè) không
        ploty_check = np.linspace(0, h - 1, 20)
        left_temp_x = lf[0] * ploty_check**2 + lf[1] * ploty_check + lf[2]
        right_temp_x = rf[0] * ploty_check**2 + rf[1] * ploty_check + rf[2]
        
        # Nếu cắt nhau (phía trái lấn sang phải), từ chối frame nhiễu này và tái sử dụng dữ liệu lịch sử ổn định
        if np.any(left_temp_x >= right_temp_x):
            if len(self._left_a) > 0:
                # Lấy trực tiếp trạng thái mượt mà cuối cùng trong bộ đệm EMA
                if hasattr(self, '_left_ema'):
                    lf_ = self._left_ema
                    rf_ = self._right_ema
                else:
                    lf_ = np.array([np.mean(self._left_a),  np.mean(self._left_b),  np.mean(self._left_c)])
                    rf_ = np.array([np.mean(self._right_a), np.mean(self._right_b), np.mean(self._right_c)])
                ploty      = np.linspace(0, h - 1, h)
                left_fitx  = lf_[0] * ploty**2 + lf_[1] * ploty + lf_[2]
                right_fitx = rf_[0] * ploty**2 + rf_[1] * ploty + rf_[2]
                return left_fitx, right_fitx, ploty, lf_, rf_
            else:
                return None

        # Lưu hệ số vào buffer
        self._left_a.append(lf[0]);  self._left_b.append(lf[1]);  self._left_c.append(lf[2])
        self._right_a.append(rf[0]); self._right_b.append(rf[1]); self._right_c.append(rf[2])

        # Cắt buffer theo n frame
        for buf in (self._left_a, self._left_b, self._left_c,
                    self._right_a, self._right_b, self._right_c):
            if len(buf) > self._n:
                buf.pop(0)

        # Hệ số trung bình của lịch sử
        lf_raw = np.array([np.mean(self._left_a),  np.mean(self._left_b),  np.mean(self._left_c)])
        rf_raw = np.array([np.mean(self._right_a), np.mean(self._right_b), np.mean(self._right_c)])

        # Tối ưu nâng cao: Áp dụng Lọc số mũ (EMA) để triệt tiêu hoàn toàn rung lắc
        if not hasattr(self, '_left_ema'):
            self._left_ema = lf_raw
            self._right_ema = rf_raw
        else:
            alpha = 0.06  # Giá trị 0.06 giúp làn đường bám cực kỳ đầm, mượt và vững chãi
            self._left_ema = alpha * lf_raw + (1 - alpha) * self._left_ema
            self._right_ema = alpha * rf_raw + (1 - alpha) * self._right_ema

        lf_ = self._left_ema
        rf_ = self._right_ema

        ploty      = np.linspace(0, h - 1, h)
        left_fitx  = lf_[0] * ploty**2 + lf_[1] * ploty + lf_[2]
        right_fitx = rf_[0] * ploty**2 + rf_[1] * ploty + rf_[2]

        return left_fitx, right_fitx, ploty, lf_, rf_

    # ── Tính toán offset & curvature ────────────────────────────────────────
    def _compute_metrics(
        self,
        img_h: int,
        img_w: int,
        left_fitx: np.ndarray,
        right_fitx: np.ndarray,
        ploty: np.ndarray,
    ) -> tuple:
        """
        Trả về (lane_offset_m, curvature_m, direction).
        """
        ym_per_pix = 30.0 / img_h

        # Kẹp chiều rộng làn trong phạm vi hợp lý (50px ~ 95% img_w)
        # Tránh trường hợp lane nhận diện sai → lane_width_px quá nhỏ → xm_per_pix bị phóng to
        lane_width_px = float(right_fitx[-1] - left_fitx[-1])
        lane_width_px = max(lane_width_px, img_w * 0.2)
        lane_width_px = min(lane_width_px, img_w * 0.95)
        xm_per_pix = self.lane_width_meters / lane_width_px

        y_eval = np.max(ploty)

        # Fit lại trong không gian thực (mét)
        lf_cr = np.polyfit(ploty * ym_per_pix, left_fitx  * xm_per_pix, 2)
        rf_cr = np.polyfit(ploty * ym_per_pix, right_fitx * xm_per_pix, 2)

        # Curvature tại điểm đáy ảnh
        left_curv  = ((1 + (2*lf_cr[0]*y_eval*ym_per_pix + lf_cr[1])**2)**1.5) / abs(2*lf_cr[0] + 1e-6)
        right_curv = ((1 + (2*rf_cr[0]*y_eval*ym_per_pix + rf_cr[1])**2)**1.5) / abs(2*rf_cr[0] + 1e-6)
        curvature  = round((left_curv + right_curv) / 2, 1)

        # Offset xe so với tâm làn (tính trong bird's-eye view)
        lane_center_px = (left_fitx[-1] + right_fitx[-1]) / 2
        vehicle_px     = img_w / 2
        offset_m       = round((vehicle_px - lane_center_px) * xm_per_pix, 3)

        if offset_m > 0.35:
            direction = "RIGHT"
        elif offset_m < -0.35:
            direction = "LEFT"
        else:
            direction = "CENTER"

        return offset_m, curvature, direction

    # ── Vẽ overlay lên ảnh gốc ─────────────────────────────────────────────
    def draw_lane_overlay(
        self,
        orig_frame: np.ndarray,
        left_fitx: np.ndarray,
        right_fitx: np.ndarray,
        ploty: np.ndarray,
        lane_offset: float,
        direction: str,
        lane_color: tuple = (0, 200, 0),
        distance_alert: str = "SAFE",
    ) -> np.ndarray:
        """
        Vẽ vùng làn đường (fillPoly) + vạch biên trái/phải + HUD lên ảnh gốc.
        Kết hợp inverse perspective warp để overlay đúng góc camera.
        """
        h, w = orig_frame.shape[:2]
        color_img = np.zeros((h, w, 3), dtype=np.uint8)

        # Cắt polygon: chỉ vẽ từ 60% chiều cao ảnh trở xuống (tránh kéo dài tới đường chân trời)
        y_start = int(h * 0.60)
        mask_y = ploty >= y_start
        ploty_clip   = ploty[mask_y]
        left_clip    = left_fitx[mask_y]
        right_clip   = right_fitx[mask_y]

        if len(ploty_clip) < 2:
            ploty_clip = ploty
            left_clip  = left_fitx
            right_clip = right_fitx

        # Tạo polygon làn đường
        left_pts  = np.array([np.transpose(np.vstack([left_clip,  ploty_clip]))])
        right_pts = np.array([np.flipud(np.transpose(np.vstack([right_clip, ploty_clip])))])
        lane_pts  = np.hstack((left_pts, right_pts))
        cv2.fillPoly(color_img, np.int_(lane_pts), lane_color)

        # Inverse warp overlay về góc camera
        inv = self._inv_perspective_warp(color_img, (w, h))
        result = cv2.addWeighted(orig_frame, 1.0, inv, 0.35, 0)

        # Vẽ chấm biên chỉ trong vùng đã cắt (nhất quán với polygon)
        for y_i, (lx, rx) in enumerate(zip(left_clip[::8], right_clip[::8])):
            y_i_real = int(ploty_clip[y_i * 8] if y_i * 8 < len(ploty_clip) else ploty_clip[-1])
            pt_l = self._warp_point_inv((int(lx), y_i_real), (w, h))
            pt_r = self._warp_point_inv((int(rx), y_i_real), (w, h))
            if pt_l and pt_r:
                cv2.circle(result, pt_l, 2, (150, 100, 255), -1)
                cv2.circle(result, pt_r, 2, (255, 100, 150), -1)

        # HUD mới: gauge bar + badge (thay thế text thô cũ)
        draw_hud(
            result,
            lane_offset=lane_offset,
            direction=direction,
            distance_alert=distance_alert,
            lane_detected=True,
        )

        return result

    def _warp_point_inv(self, pt: tuple, frame_size: tuple):
        """Biến đổi ngược 1 điểm từ bird's-eye view về góc camera."""
        try:
            w, h = frame_size
            img_size = np.float32([(w, h)])
            src = self.dst_pts * img_size
            dst = self.src_pts * np.float32([(w, h)])
            M = cv2.getPerspectiveTransform(src, dst)
            pt_arr = np.array([[[pt[0], pt[1]]]], dtype=np.float32)
            warped = cv2.perspectiveTransform(pt_arr, M)
            return (int(warped[0][0][0]), int(warped[0][0][1]))
        except Exception:
            return None

    def _get_lane_color_and_alert(
        self,
        img_h: int,
        img_w: int,
        detections: list[dict] = None,
    ) -> tuple[tuple[int, int, int], str]:
        """
        Xác định màu sắc cho làn đường và cảnh báo khoảng cách dựa trên các phương tiện phía trước.
        - Trả về: (color_bgr, alert_text)
        - 3 mức độ:
          1. ĐỎ (Nguy hiểm - Rất gần): khi có xe cùng làn có y2 > 0.8 * h
          2. VÀNG (Cảnh báo - Gần vừa): khi có xe cùng làn có y2 > 0.65 * h và <= 0.8 * h
          3. XANH (An toàn - Xa hoặc không có xe): mặc định
        """
        default_color = (0, 200, 0)
        if not detections:
            return default_color, "SAFE"

        closest_y2 = 0
        vehicle_in_lane = False
        frame_cx = img_w / 2

        for det in detections:
            if det["class_name"] not in ["car", "truck", "bus", "motorcycle"]:
                continue
            bbox = det["bbox"]
            x_center = (bbox["x1"] + bbox["x2"]) / 2
            y_bottom  = bbox["y2"]

            # Kiểm tra xe nằm trong ~25% trung tâm ngang của frame (tọa độ camera gốc)
            if abs(x_center - frame_cx) < img_w * 0.25:
                vehicle_in_lane = True
                if y_bottom > closest_y2:
                    closest_y2 = y_bottom

        if not vehicle_in_lane:
            return default_color, "SAFE"

        if closest_y2 > 0.80 * img_h:
            return (0, 0, 255),   "DANGER"
        elif closest_y2 > 0.65 * img_h:
            return (0, 255, 255), "WARNING"
        else:
            return default_color, "SAFE"

    # ── Public API ─────────────────────────────────────────────────────────
    def analyze_lane(
        self,
        lane_marking_mask: np.ndarray,
        orig_frame: np.ndarray = None,
        detections: list[dict] = None,
    ) -> dict:
        """
        Phân tích đường làn từ mask vạch kẻ (đầu ra DeepLab).

        Args:
            lane_marking_mask: ảnh nhị phân (0/255) vạch kẻ đường, hoặc BGR frame.
            orig_frame:        ảnh gốc BGR để vẽ overlay (tùy chọn).
        Returns:
            dict với lane_detected, lane_offset, direction, curvature,
                  left_line (pts), right_line (pts), overlay_frame.
        """
        h, w = lane_marking_mask.shape[:2]

        # Bước 1: Threshold
        binary = self._threshold(lane_marking_mask)

        # Bước 2: Bird's-eye warp
        warped = self._perspective_warp(binary)

        # Bước 3: Sliding window
        result = self._sliding_window(warped)
        if result is None:
            return {
                "lane_detected":  False,
                "lane_offset":    None,
                "direction":      "UNKNOWN",
                "curvature_m":    None,
                "left_line":      None,
                "right_line":     None,
                "overlay_frame":  orig_frame,
                "distance_alert": "UNKNOWN",
            }

        left_fitx, right_fitx, ploty, lf_, rf_ = result

        # Bộ lọc chống giao cắt bổ sung (Defense in Depth)
        if np.any(left_fitx >= right_fitx):
            return {
                "lane_detected":  False,
                "lane_offset":    None,
                "direction":      "UNKNOWN",
                "curvature_m":    None,
                "left_line":      None,
                "right_line":     None,
                "overlay_frame":  orig_frame,
                "distance_alert": "UNKNOWN",
            }

        # Bước 4: Tính offset và curvature
        offset_m, curvature_m, direction = self._compute_metrics(h, w, left_fitx, right_fitx, ploty)

        # Xác định màu sắc làn đường dựa trên khoảng cách xe cùng làn
        lane_color, distance_alert = self._get_lane_color_and_alert(
            h, w, detections
        )

        # Bước 5: Tạo điểm hiển thị trên ảnh gốc (phục vụ vẽ đường thẳng fallback)
        y_bot   = int(ploty[-1])
        y_top   = int(ploty[len(ploty) // 3])
        
        pt_l_top = self._warp_point_inv((int(left_fitx[len(ploty) // 3]), y_top), (w, h))
        pt_l_bot = self._warp_point_inv((int(left_fitx[-1]), y_bot), (w, h))
        pt_r_top = self._warp_point_inv((int(right_fitx[len(ploty) // 3]), y_top), (w, h))
        pt_r_bot = self._warp_point_inv((int(right_fitx[-1]), y_bot), (w, h))
        
        left_line  = (pt_l_top, pt_l_bot) if (pt_l_top and pt_l_bot) else None
        right_line = (pt_r_top, pt_r_bot) if (pt_r_top and pt_r_bot) else None

        # Bước 6: Vẽ overlay
        overlay = None
        if orig_frame is not None:
            overlay = self.draw_lane_overlay(
                orig_frame, left_fitx, right_fitx, ploty, offset_m, direction,
                lane_color=lane_color, distance_alert=distance_alert
            )

        return {
            "lane_detected":  True,
            "lane_offset":    offset_m,
            "direction":      direction,
            "curvature_m":    curvature_m,
            "left_line":      left_line,
            "right_line":     right_line,
            "overlay_frame":  overlay,
            "distance_alert": distance_alert,
        }
