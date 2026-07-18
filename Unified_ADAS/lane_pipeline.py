import cv2
import numpy as np
from lane_core.yolo_detector import YOLODetector
from lane_core.deeplab_segmenter import DeepLabSegmenter
from lane_core.hough_lane import HoughLaneDetector
from lane_core.geometry import LaneGeometry
from lane_core.fusion import DataFusion
from lane_core.hud import draw_hud
from lane_event_client import EventClient


class LanePipeline:
    """
    Pipeline hợp nhất xử lý ADAS — Cải tiến với Dual-Mode Lane Detection:

    Chế độ CHÍNH (Primary): HoughLaneDetector
      - Grayscale → Dilation → Canny → ROI → HoughLinesP → Weighted Average
      - Nhanh hơn, phù hợp realtime, inspired từ 3 file tham khảo

    Chế độ DỰ PHÒNG (Fallback): LaneGeometry (Sliding Window)
      - Bird's-eye Perspective Warp + Sliding Window + Polynomial Fit bậc 2
      - Chính xác hơn cho đường cong, dùng khi Hough không phát hiện được làn

    Các bước:
      1. YOLO: Nhận diện vật cản (xe, xe máy, …)
      2. DeepLab: Tạo lane marking mask (HSV + Canny kết hợp)
      3. Fusion:  Loại bỏ vật cản khỏi drivable area
      4. Hough:   Phát hiện và average lines trái/phải (PRIMARY)
      5. Geometry: Sliding Window + Poly Fit làm dự phòng / tính curvature
      6. EventClient: Gửi cảnh báo chệch làn
    """

    def __init__(self, yolo_detector: YOLODetector = None):
        self.yolo_detector  = yolo_detector or YOLODetector()
        self.deeplab        = DeepLabSegmenter()
        self.hough          = HoughLaneDetector(
            canny_low=60,
            canny_high=200,
            hough_threshold=40,
            min_line_length=10,
            max_line_gap=5,
            roi_top_ratio=0.60,
        )
        self.geometry       = LaneGeometry()
        self.fusion         = DataFusion()
        self.event_client   = EventClient()

    def process_frame(self, frame: np.ndarray, visualize: bool = False) -> dict:
        """
        Xử lý một frame qua toàn bộ ADAS pipeline.

        Args:
            frame:     Frame BGR từ OpenCV.
            visualize: Nếu True, vẽ overlay lên frame gốc (in-place).

        Returns:
            dict với đầy đủ thông tin phát hiện và trạng thái làn.
        """
        height, width = frame.shape[:2]

        # ── Bước 1: YOLO — Nhận diện vật cản ──────────────────────────────
        detections = self.yolo_detector.detect(frame)

        # ── Bước 2: DeepLab — Phân vùng đường & vạch kẻ ───────────────────
        drivable_mask, lane_mask = self.deeplab.segment(frame)

        # ── Bước 3: Fusion — Loại bỏ vật cản khỏi drivable area ───────────
        fused_drivable = self.fusion.fuse(drivable_mask, detections)

        # ── Bước 4: Hough — Phát hiện làn chính (PRIMARY) ──────────────────
        hough_result = self.hough.detect(frame)
        hough_offset, hough_direction = self.hough.compute_offset(
            hough_result["left_line"],
            hough_result["right_line"],
            frame_w=width,
        )
        hough_detected = hough_result["lane_detected"]

        # ── Bước 5: Geometry — Sliding Window (FALLBACK / curvature) ───────
        geo_info = self.geometry.analyze_lane(
            lane_mask,
            orig_frame=frame if visualize else None,
            detections=detections,
        )
        geo_detected = geo_info["lane_detected"]

        # ── Tổng hợp kết quả: ưu tiên Hough, fallback sang Geometry ────────
        if hough_detected:
            lane_detected = True
            lane_offset   = hough_offset
            direction     = hough_direction
            curvature_m   = geo_info.get("curvature_m")  # Lấy curvature từ Geometry nếu có
        elif geo_detected:
            lane_detected = True
            lane_offset   = geo_info["lane_offset"]
            direction     = geo_info["direction"]
            curvature_m   = geo_info.get("curvature_m")
        else:
            lane_detected = False
            lane_offset   = None
            direction     = "UNKNOWN"
            curvature_m   = None

        # Xác định mức cảnh báo khoảng cách
        distance_alert = geo_info.get("distance_alert", "SAFE") if geo_detected \
                         else self._compute_distance_alert(detections, height, width)

        # ── Bước 6: EventClient — Gửi cảnh báo chệch làn ──────────────────
        if lane_detected and direction in ("LEFT", "RIGHT") and lane_offset is not None:
            self.event_client.send_departure_warning(
                lane_offset=lane_offset,
                direction=direction,
            )

        # ── Bước 7: Vẽ overlay trực quan hóa ──────────────────────────────
        if visualize:
            self._draw_visualization(
                frame=frame,
                hough_result=hough_result,
                geo_info=geo_info,
                detections=detections,
                fused_drivable=fused_drivable,
                lane_detected=lane_detected,
                lane_offset=lane_offset if lane_offset is not None else 0.0,
                direction=direction,
                distance_alert=distance_alert,
                hough_detected=hough_detected,
            )

        return {
            "frame_width":    width,
            "frame_height":   height,
            "detections":     detections,
            "num_detections": len(detections),
            "lane_detected":  lane_detected,
            "lane_offset":    lane_offset,
            "direction":      direction,
            "curvature_m":    curvature_m,
            "distance_alert": distance_alert,
            "hough_detected": hough_detected,
            "geo_detected":   geo_detected,
            "message":        "Full ADAS pipeline: YOLO + Hough (primary) + Sliding Window (fallback)",
        }

    # ── Helper: Vẽ overlay ────────────────────────────────────────────────────
    def _draw_visualization(
        self,
        frame: np.ndarray,
        hough_result: dict,
        geo_info: dict,
        detections: list,
        fused_drivable: np.ndarray,
        lane_detected: bool,
        lane_offset: float,
        direction: str,
        distance_alert: str,
        hough_detected: bool,
    ) -> None:
        """Vẽ overlay lên frame gốc (in-place) theo thứ tự ưu tiên."""

        # ── Ưu tiên 1: Hough overlay (fast, clean) ─────────────────────────
        if hough_detected:
            result = self.hough.draw_overlay(
                frame=frame,
                hough_result=hough_result,
                lane_offset=lane_offset,
                direction=direction,
                distance_alert=distance_alert,
                draw_raw_lines=False,
            )
            frame[:] = result[:]

        # ── Fallback: Geometry overlay (Sliding Window + inverse warp) ─────
        elif geo_info.get("overlay_frame") is not None:
            frame[:] = geo_info["overlay_frame"][:]

        # ── Last resort: Drivable area tô màu xanh nhạt ────────────────────────
        else:
            overlay = frame.copy()
            overlay[fused_drivable == 255] = [0, 200, 60]
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

            # HUD khi không có làn
            draw_hud(
                frame,
                lane_offset=None,
                direction="UNKNOWN",
                distance_alert=distance_alert,
                lane_detected=False,
            )

        # ── Luôn vẽ YOLO bounding boxes lên trên overlay ──────────────────
        for det in detections:
            bbox = det["bbox"]
            x1 = int(bbox["x1"]); y1 = int(bbox["y1"])
            x2 = int(bbox["x2"]); y2 = int(bbox["y2"])
            label = f"{det['class_name']} {det['confidence']:.2f}"
            color = (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 5), (x1 + tw, y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # ── Helper: tính distance_alert từ YOLO detections ───────────────────────
    def _compute_distance_alert(
        self, detections: list, frame_h: int, frame_w: int
    ) -> str:
        """Tính mức cảnh báo khoảng cách khi Geometry không chạy được."""
        cx = frame_w / 2
        closest_y2 = 0
        in_lane = False

        for det in detections:
            if det["class_name"] not in ["car", "truck", "bus", "motorcycle"]:
                continue
            bbox = det["bbox"]
            x_center = (bbox["x1"] + bbox["x2"]) / 2
            y_bottom  = bbox["y2"]

            if abs(x_center - cx) < frame_w * 0.25:
                in_lane = True
                if y_bottom > closest_y2:
                    closest_y2 = y_bottom

        if not in_lane:
            return "SAFE"
        if closest_y2 > 0.80 * frame_h:
            return "DANGER"
        if closest_y2 > 0.65 * frame_h:
            return "WARNING"
        return "SAFE"
