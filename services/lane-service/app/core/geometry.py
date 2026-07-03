import cv2
import numpy as np

class LaneGeometry:
    """
    Xử lý hình học đường biên làn để xác định tâm làn đường,
    độ lệch tâm xe (lane_offset) và hướng chệch làn.
    """
    def __init__(self, lane_width_meters: float = 3.7):
        self.lane_width_meters = lane_width_meters

    def analyze_lane(self, lane_marking_mask: np.ndarray) -> dict:
        """
        Phân tích vạch kẻ đường để tìm độ chênh lệch lane_offset.
        """
        height, width = lane_marking_mask.shape[:2]
        mid_x = int(width / 2)
        
        # 1. Phân tách điểm của vạch kẻ bên trái và bên phải
        # Chỉ xét vùng vạch kẻ nửa dưới ảnh
        roi_y_start = int(height * 0.55)
        
        # Trích xuất điểm vạch kẻ bên trái (nửa bên trái ảnh)
        left_y, left_x = np.where(lane_marking_mask[roi_y_start:, :mid_x] == 255)
        left_y = left_y + roi_y_start # Bù lại offset trục y
        
        # Trích xuất điểm vạch kẻ bên phải (nửa bên phải ảnh)
        right_y, right_x = np.where(lane_marking_mask[roi_y_start:, mid_x:] == 255)
        right_y = right_y + roi_y_start
        right_x = right_x + mid_x # Bù lại offset trục x
        
        left_fit = None
        right_fit = None
        
        # Cần tối thiểu 50 điểm để khớp đường thẳng tin cậy
        if len(left_x) > 50:
            left_fit = np.polyfit(left_y, left_x, 1) # x = ay + b
            
        if len(right_x) > 50:
            right_fit = np.polyfit(right_y, right_x, 1) # x = ay + b
            
        lane_detected = False
        lane_offset_meters = None
        direction = "UNKNOWN"
        left_line_pts = None
        right_line_pts = None
        
        # Tính toán tọa độ tại đáy ảnh (y = height) và phần đỉnh làn (y = roi_y_start)
        y_bottom = height
        y_top = roi_y_start
        
        left_x_bottom = None
        right_x_bottom = None
        
        if left_fit is not None:
            left_x_bottom = int(left_fit[0] * y_bottom + left_fit[1])
            left_x_top = int(left_fit[0] * y_top + left_fit[1])
            left_line_pts = ((left_x_top, y_top), (left_x_bottom, y_bottom))
            
        if right_fit is not None:
            right_x_bottom = int(right_fit[0] * y_bottom + right_fit[1])
            right_x_top = int(right_fit[0] * y_top + right_fit[1])
            right_line_pts = ((right_x_top, y_top), (right_x_bottom, y_bottom))

        # Nếu phát hiện đủ cả 2 vạch đường biên trái và phải
        if left_x_bottom is not None and right_x_bottom is not None:
            lane_detected = True
            
            # Chiều rộng làn tính bằng pixel tại đáy ảnh
            lane_width_pixels = right_x_bottom - left_x_bottom
            
            if lane_width_pixels > 100: # Tránh lỗi chia cho 0 hoặc làn quá hẹp
                # Tỷ lệ đổi: mét / pixel
                meters_per_pixel = self.lane_width_meters / lane_width_pixels
                
                # Tính tâm làn đường ở đáy ảnh
                lane_center_pixel = (left_x_bottom + right_x_bottom) / 2
                
                # Tâm xe (giả định là trục dọc chính giữa camera)
                vehicle_center_pixel = width / 2
                
                # Độ lệch (dương là lệch phải, âm là lệch trái)
                offset_pixels = vehicle_center_pixel - lane_center_pixel
                lane_offset_meters = round(offset_pixels * meters_per_pixel, 2)
                
                # Xác định hướng chệch làn dựa trên ngưỡng 0.2 mét
                if lane_offset_meters > 0.2:
                    direction = "RIGHT"
                elif lane_offset_meters < -0.2:
                    direction = "LEFT"
                else:
                    direction = "CENTER"
                    
        # Nếu chỉ phát hiện một bên làn đường, giả lập bán khoảng làn đường
        elif left_x_bottom is not None or right_x_bottom is not None:
            lane_detected = True
            direction = "CENTER" # Fallback mặc định
            
        return {
            "lane_detected": lane_detected,
            "lane_offset": lane_offset_meters,
            "direction": direction,
            "left_line": left_line_pts,
            "right_line": right_line_pts
        }
