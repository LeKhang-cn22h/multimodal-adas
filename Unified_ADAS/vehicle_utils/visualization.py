import cv2
import numpy as np
import vehicle_config as config

class Visualizer:
    """
    Hỗ trợ hiển thị và vẽ giao diện trực quan lên frame
    """
    @staticmethod
    def draw_box_and_label(frame, box, track_id, class_name, distance, color):
        """
        Vẽ Bounding Box và in thông tin lên hình ảnh.
        """
        x1, y1, x2, y2 = map(int, box)
        
        # Vẽ hộp bao (Bounding Box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Chuẩn bị nội dung hiển thị
        label = f"ID:{track_id} {class_name} {distance:.1f}m"
        
        # Vẽ nền cho text để dễ nhìn hơn
        (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - text_height - 10), (x1 + text_width, y1), color, -1)
        
        # In text
        cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
    @staticmethod
    def draw_hud(frame, fps, global_risk_level="low"):
        """
        Vẽ thông tin HUD (Head-Up Display) chung của hệ thống.
        """
        h, w = frame.shape[:2]
        # Move to top right corner
        start_x = w - 450
        start_y = 20
        
        # Hiển thị FPS
        cv2.putText(frame, f"FPS: {fps:.1f}", (start_x, start_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Hiển thị trạng thái nguy cơ hệ thống
        risk_color = (0, 255, 0)
        risk_text = "AN TOAN"
        
        if global_risk_level == "critical":
            risk_color = (0, 0, 255)
            risk_text = "NGUY HIEM CAP BACH (CRITICAL)"
        elif global_risk_level == "high":
            risk_color = (0, 0, 255)
            risk_text = "NGUY HIEM CAO (HIGH)"
        elif global_risk_level == "medium":
            risk_color = (0, 255, 255)
            risk_text = "CANH BAO (WARNING)"
            
        cv2.rectangle(frame, (start_x, start_y + 30), (start_x + 430, start_y + 65), (0, 0, 0), -1) # Nền đen cho chữ
        cv2.putText(frame, f"ADAS STATUS: {risk_text}", (start_x + 10, start_y + 55), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, risk_color, 2, cv2.LINE_AA)

    @staticmethod
    def draw_zones(frame, h, w):
        """
        Vẽ đường phân chia các vùng khoảng cách dưới dạng đường quét 3D (Trapezoid Projection Grid)
        và đổ màu bán trong suốt cho Danger/Warning zones.
        """
        horizon_y = int(config.HORIZON_Y_PCT * h)
        
        # Danger Zone y-coordinate (8m) -> y = horizon_y + 3.0 * h / DangerDist
        y_danger = int(horizon_y + 3.0 * h / config.DANGER_ZONE_DISTANCE)
        # Warning Zone y-coordinate (22m) -> y = horizon_y + 3.0 * h / WarningDist
        y_warning = int(horizon_y + 3.0 * h / config.WARNING_ZONE_DISTANCE)
        
        # Tính toán tọa độ X của làn đường 3D ảo theo luật phối cảnh
        # Khung làn đáy (y=h)
        xl_bot = int((0.5 - config.LANE_WIDTH_BOTTOM_PCT / 2) * w)
        xr_bot = int((0.5 + config.LANE_WIDTH_BOTTOM_PCT / 2) * w)
        # Khung làn chân trời (y=horizon)
        xl_top = int((0.5 - config.LANE_WIDTH_TOP_PCT / 2) * w)
        xr_top = int((0.5 + config.LANE_WIDTH_TOP_PCT / 2) * w)
        
        # Hàm nội suy tọa độ X dựa trên Y
        def get_x_bounds(y):
            t = (y - horizon_y) / (h - horizon_y) if h != horizon_y else 0
            xl = int(xl_top + t * (xl_bot - xl_top))
            xr = int(xr_top + t * (xr_bot - xr_top))
            return xl, xr
            
        xl_warn, xr_warn = get_x_bounds(y_warning)
        xl_dang, xr_dang = get_x_bounds(y_danger)
        
        # Tạo bản sao vẽ bán trong suốt
        overlay = frame.copy()
        
        # 1. Đổ màu Vùng Cảnh báo (Warning Zone - Màu vàng nhạt)
        pts_warn = np.array([
            [xl_warn, y_warning],
            [xr_warn, y_warning],
            [xr_dang, y_danger],
            [xl_dang, y_danger]
        ], dtype=np.int32)
        cv2.fillPoly(overlay, [pts_warn], (0, 230, 230))
        
        # 2. Đổ màu Vùng Nguy hiểm (Danger Zone - Màu đỏ nhạt)
        pts_dang = np.array([
            [xl_dang, y_danger],
            [xr_dang, y_danger],
            [xr_bot, h],
            [xl_bot, h]
        ], dtype=np.int32)
        cv2.fillPoly(overlay, [pts_dang], (0, 0, 230))
        
        # Trộn màu bán trong suốt (Alpha = 0.15)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        
        # 3. Vẽ các đường biên giới hạn và nhãn văn bản sắc nét
        # Biên bên trái
        cv2.line(frame, (xl_warn, y_warning), (xl_bot, h), (255, 255, 255), 1, cv2.LINE_AA)
        # Biên bên phải
        cv2.line(frame, (xr_warn, y_warning), (xr_bot, h), (255, 255, 255), 1, cv2.LINE_AA)
        
        # Đường cắt Warning (22m)
        cv2.line(frame, (xl_warn, y_warning), (xr_warn, y_warning), (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, "WARNING ZONE (22m)", (xl_warn + 10, y_warning - 8), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
                    
        # Đường cắt Danger (8m)
        cv2.line(frame, (xl_dang, y_danger), (xr_dang, y_danger), (0, 0, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, "DANGER ZONE (8m)", (xl_dang + 10, y_danger - 8), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)

