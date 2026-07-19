"""
HoughLaneDetector - Nhận diện làn đường bằng Hough Transform
=============================================================
Kết hợp kỹ thuật từ 3 bộ code tham khảo:
  1. Grayscale → Dilation → Canny (thay thế thuần HSV)
  2. ROI hình thang động theo kích thước frame
  3. HoughLinesP để phát hiện đoạn thẳng
  4. Phân tách trái/phải theo slope và vị trí ngang
  5. Trung bình hóa có trọng số (weighted average) theo chiều dài line
  6. Vẽ overlay fillPoly vùng làn + đường biên trái/phải
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from core.hud import draw_hud


class HoughLaneDetector:
    """
    Nhận diện làn đường bằng Hough Lines P Transform.

    Pipeline:
        frame → Grayscale → Dilation → Canny → ROI Mask
              → HoughLinesP → Tách trái/phải → Weighted Average
              → Overlay visualization
    """

    def __init__(
        self,
        canny_low: int = 60,
        canny_high: int = 200,
        hough_threshold: int = 40,
        min_line_length: int = 10,
        max_line_gap: int = 5,
        roi_top_ratio: float = 0.60,
        slope_min: float = 0.3,
        slope_max: float = 2.5,
    ):
        """
        Args:
            canny_low:        Ngưỡng dưới Canny.
            canny_high:       Ngưỡng trên Canny.
            hough_threshold:  Số phiếu tối thiểu để giữ đường.
            min_line_length:  Độ dài tối thiểu đoạn thẳng (px).
            max_line_gap:     Khoảng cách tối đa giữa các đoạn (px).
            roi_top_ratio:    Tỷ lệ chiều cao bắt đầu ROI từ trên (0~1).
            slope_min:        Slope tối thiểu để coi là làn đường (lọc ngang).
            slope_max:        Slope tối đa để lọc bỏ đường quá dốc.
        """
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.hough_threshold = hough_threshold
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
        self.roi_top_ratio = roi_top_ratio
        self.slope_min = slope_min
        self.slope_max = slope_max
        self._dilation_kernel = np.ones((3, 3), np.uint8)

        # Buffer trung bình hóa qua nhiều frame để giảm nhiễu (rolling average)
        self._left_buffer:  List[Tuple] = []   # [(slope, intercept, weight), ...]
        self._right_buffer: List[Tuple] = []
        self._buffer_size = 5

    # ── Bước 1: Tạo edge map ────────────────────────────────────────────────
    def _make_edge_map(self, frame: np.ndarray) -> np.ndarray:
        """
        Grayscale → Dilation → Canny.
        Kỹ thuật từ 3 file tham khảo: làm mờ nhiễu trước khi Canny giúp
        giảm edge giả, giữ lại viền vạch kẻ sắc nét hơn.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dilated = cv2.dilate(gray, kernel=self._dilation_kernel)
        return cv2.Canny(dilated, self.canny_low, self.canny_high)

    # ── Bước 2: ROI hình thang ───────────────────────────────────────────────
    def _get_roi_vertices(self, h: int, w: int) -> np.ndarray:
        """
        Tính ROI động theo kích thước frame (hình thang hướng về điểm tụ).
        Tham khảo từ detection_on_image + nyc_lane_detection.
        """
        y_top = int(h * self.roi_top_ratio)
        return np.array([[
            (int(w * 0.10), h),           # Bottom-left
            (int(w * 0.45), y_top),       # Top-left  (gần điểm tụ)
            (int(w * 0.55), y_top),       # Top-right (gần điểm tụ)
            (int(w * 0.90), h),           # Bottom-right
        ]], dtype=np.int32)

    def _apply_roi(self, edge_map: np.ndarray, vertices: np.ndarray) -> np.ndarray:
        """Áp dụng mặt nạ ROI lên edge map."""
        mask = np.zeros_like(edge_map)
        cv2.fillPoly(mask, vertices, 255)
        return cv2.bitwise_and(edge_map, mask)

    # ── Bước 3: Tách và lọc đường trái/phải ────────────────────────────────
    def _separate_and_filter(
        self,
        lines: np.ndarray,
        h: int,
        w: int,
    ) -> Tuple[List, List]:
        """
        Phân tách lines thô thành 2 nhóm: trái (slope âm) và phải (slope dương).
        Lọc theo:
          - Slope: loại đường ngang (quá nhỏ) và đường gần dọc (quá dốc)
          - Vị trí ngang: đường trái phải nằm bên trái trung tâm và ngược lại
        """
        left_lines: List[Tuple[float, float, float]] = []   # (slope, intercept, length)
        right_lines: List[Tuple[float, float, float]] = []
        mid_x = w / 2

        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = x2 - x1
            if dx == 0:
                continue  # Bỏ đường hoàn toàn dọc

            slope = (y2 - y1) / dx
            if abs(slope) < self.slope_min or abs(slope) > self.slope_max:
                continue  # Lọc đường ngang / quá dốc

            intercept = y1 - slope * x1
            length = float(np.hypot(dx, y2 - y1))

            # Đường trái: slope âm, x1 và x2 đều bên trái trung tâm
            if slope < 0 and max(x1, x2) < mid_x * 1.1:
                left_lines.append((slope, intercept, length))
            # Đường phải: slope dương, x1 và x2 đều bên phải trung tâm
            elif slope > 0 and min(x1, x2) > mid_x * 0.9:
                right_lines.append((slope, intercept, length))

        return left_lines, right_lines

    # ── Bước 4: Trung bình hóa có trọng số ─────────────────────────────────
    def _weighted_average(
        self,
        lines: List[Tuple[float, float, float]],
        buffer: List[Tuple],
        y_bottom: int,
        y_top: int,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Tính đường trung bình có trọng số theo chiều dài từng line.
        Dùng rolling buffer qua nhiều frame để đường hiển thị mượt hơn.
        """
        if lines:
            total_len = sum(l[2] for l in lines)
            if total_len > 0:
                avg_slope = sum(l[0] * l[2] for l in lines) / total_len
                avg_int   = sum(l[1] * l[2] for l in lines) / total_len
                buffer.append((avg_slope, avg_int))
                if len(buffer) > self._buffer_size:
                    buffer.pop(0)

        if not buffer:
            return None

        # Trung bình qua buffer
        slope = np.mean([b[0] for b in buffer])
        intercept = np.mean([b[1] for b in buffer])

        if abs(slope) < 1e-6:
            return None

        x_bot = int((y_bottom - intercept) / slope)
        x_top = int((y_top    - intercept) / slope)
        return (x_bot, y_bottom, x_top, y_top)

    # ── Public API: detect ───────────────────────────────────────────────────
    def detect(self, frame: np.ndarray) -> dict:
        """
        Phát hiện làn đường từ một frame BGR.

        Returns:
            dict:
                lines_raw   : list of [x1,y1,x2,y2] thô từ HoughLinesP
                left_line   : (x1,y1,x2,y2) | None — đường làn trái averaged
                right_line  : (x1,y1,x2,y2) | None — đường làn phải averaged
                edge_map    : Canny edge image (HxW)
                roi_image   : edge map sau khi cắt ROI (HxW)
                lane_detected: bool
        """
        h, w = frame.shape[:2]
        y_top    = int(h * self.roi_top_ratio)
        y_bottom = h

        # 1. Edge map
        edges = self._make_edge_map(frame)

        # 2. ROI
        vertices = self._get_roi_vertices(h, w)
        roi_img = self._apply_roi(edges, vertices)

        # 3. Hough Lines P
        lines = cv2.HoughLinesP(
            roi_img,
            rho=1,
            theta=np.pi / 180,
            threshold=self.hough_threshold,
            minLineLength=self.min_line_length,
            maxLineGap=self.max_line_gap,
        )

        if lines is None:
            return {
                "lines_raw":    [],
                "left_line":    None,
                "right_line":   None,
                "edge_map":     edges,
                "roi_image":    roi_img,
                "lane_detected": False,
            }

        # 4. Tách và lọc trái/phải
        left_raw, right_raw = self._separate_and_filter(lines, h, w)

        # 5. Trung bình hóa (có rolling buffer)
        left_line  = self._weighted_average(left_raw,  self._left_buffer,  y_bottom, y_top)
        right_line = self._weighted_average(right_raw, self._right_buffer, y_bottom, y_top)

        return {
            "lines_raw":    [l.tolist() for l in lines],
            "left_line":    left_line,
            "right_line":   right_line,
            "edge_map":     edges,
            "roi_image":    roi_img,
            "lane_detected": (left_line is not None) or (right_line is not None),
        }

    # ── Public API: draw_overlay ─────────────────────────────────────────────
    def draw_overlay(
        self,
        frame: np.ndarray,
        hough_result: dict,
        lane_offset: float = 0.0,
        direction: str = "CENTER",
        distance_alert: str = "SAFE",
        draw_raw_lines: bool = False,
    ) -> np.ndarray:
        """
        Vẽ kết quả Hough lên frame BGR.

        Features:
          - Vùng làn fillPoly (màu theo distance_alert)
          - Đường biên trái (đỏ) / phải (xanh dương)
          - HUD: Offset + Alert
          - Tùy chọn: vẽ tất cả lines thô
        """
        result = frame.copy()

        left  = hough_result.get("left_line")
        right = hough_result.get("right_line")
        lane_detected = hough_result.get("lane_detected", False)

        # ── Màu vùng làn theo mức cảnh báo khoảng cách ──────────────────
        if distance_alert == "DANGER":
            fill_color = (30, 30, 200)
        elif distance_alert == "WARNING":
            fill_color = (20, 190, 200)
        else:
            fill_color = (0, 180, 0)

        # ── Tùy chọn: vẽ lines thô ───────────────────────────────────────
        if draw_raw_lines:
            for seg in hough_result.get("lines_raw", []):
                x1, y1, x2, y2 = seg[0]
                cv2.line(result, (x1, y1), (x2, y2), (0, 180, 90), 1)

        # ── fillPoly vùng làn ─────────────────────────────────────────────
        if left and right:
            pts = np.array([
                [left[0],  left[1]],
                [left[2],  left[3]],
                [right[2], right[3]],
                [right[0], right[1]],
            ], dtype=np.int32)
            poly_overlay = result.copy()
            cv2.fillPoly(poly_overlay, [pts], fill_color)
            cv2.addWeighted(poly_overlay, 0.28, result, 0.72, 0, result)

        # ── Đường biên trái/phải ─────────────────────────────────────────
        if left:
            cv2.line(result, (left[0],  left[1]),  (left[2],  left[3]),
                     (100, 100, 255), 4, cv2.LINE_AA)
        if right:
            cv2.line(result, (right[0], right[1]), (right[2], right[3]),
                     (255, 100, 100), 4, cv2.LINE_AA)

        # ── HUD mới: gauge bar + badge ────────────────────────────────────
        draw_hud(
            result,
            lane_offset=lane_offset,
            direction=direction,
            distance_alert=distance_alert,
            lane_detected=lane_detected,
        )

        return result

    # ── Tính lane offset từ Hough lines ─────────────────────────────────────
    def compute_offset(
        self,
        left_line:  Optional[Tuple],
        right_line: Optional[Tuple],
        frame_w: int,
        lane_width_m: float = 3.7,
    ) -> Tuple[float, str]:
        """
        Tính lane offset (mét) và direction từ Hough lines.

        Returns:
            (offset_m, direction): offset dương → lệch phải, âm → lệch trái.
        """
        if left_line is None and right_line is None:
            return 0.0, "UNKNOWN"

        frame_cx = frame_w / 2.0

        if left_line and right_line:
            # Tâm làn = trung điểm 2 đường ở đáy frame
            lane_cx = (left_line[0] + right_line[0]) / 2.0
            lane_width_px = abs(right_line[0] - left_line[0])
            lane_width_px = max(lane_width_px, frame_w * 0.20)   # clamp
        elif left_line:
            # Chỉ có đường trái → ước tính trung tâm
            lane_cx = left_line[0] + frame_w * 0.20
            lane_width_px = frame_w * 0.50
        else:
            # Chỉ có đường phải
            lane_cx = right_line[0] - frame_w * 0.20
            lane_width_px = frame_w * 0.50

        xm_per_pix = lane_width_m / lane_width_px
        offset_m = round((frame_cx - lane_cx) * xm_per_pix, 3)

        if offset_m > 0.30:
            direction = "RIGHT"
        elif offset_m < -0.30:
            direction = "LEFT"
        else:
            direction = "CENTER"

        return offset_m, direction

    def reset_buffer(self):
        """Xóa rolling buffer (dùng khi đổi video source)."""
        self._left_buffer.clear()
        self._right_buffer.clear()
