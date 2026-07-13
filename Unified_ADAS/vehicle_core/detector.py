from ultralytics import YOLO
import vehicle_config as config

class ObjectDetector:
    """
    Module xử lý Mô hình Trí tuệ Nhân tạo (AI Core)
    """
    def __init__(self):
        self.model = YOLO(config.MODEL_PATH)
        self.target_classes = config.TARGET_CLASSES
        self.tracker_config = config.TRACKER_CONFIG
        self.rider_tracks = {} # track_id -> frames_since_last_overlap

    def track_objects(self, frame):
        """
        Chạy mô hình YOLOv11 để nhận diện và ByteTrack để theo dõi.
        Trả về kết quả chứa thông tin Bounding Box, ID, Class.
        """
        results = self.model.track(
            frame, 
            persist=True, 
            tracker=self.tracker_config, 
            classes=self.target_classes, 
            conf=config.CONFIDENCE_THRESHOLD,
            verbose=False
        )
        return results[0]

    def predict_objects(self, frame):
        """
        Chạy mô hình YOLOv11 ở chế độ nhận diện (predict) cho ảnh tĩnh.
        Trả về kết quả chứa thông tin Bounding Box, Class.
        """
        results = self.model.predict(
            frame, 
            classes=self.target_classes, 
            conf=config.CONFIDENCE_THRESHOLD,
            verbose=False
        )
        return results[0]

    def filter_inside_vehicles(self, boxes, class_ids, track_ids):
        """
        Lọc bỏ những Bounding Box của "Người đi bộ" (class 0) nếu:
        1. Nằm gọn > 30% bên trong khung của các phương tiện (Xe máy, Xe hơi, Xe buýt, Xe tải, Xe đạp).
        2. Xếp chồng dọc (Vertical Stacking): Horizontal overlap > 60% và vertical gap < 15% chiều cao người.
        3. Sử dụng bộ nhớ Temporal Rider Memory: Nếu đã được xác định là Rider trong vòng 15 frame trước.
        """
        keep_indices = []
        
        person_indices = [i for i, cls in enumerate(class_ids) if cls == 0]
        vehicle_indices = [i for i, cls in enumerate(class_ids) if cls in [1, 2, 3, 5, 7]]
        
        for i in range(len(boxes)):
            if class_ids[i] != 0:
                # Giữ lại toàn bộ phương tiện
                keep_indices.append(i)
            else:
                person_box = boxes[i]
                x1_p, y1_p, x2_p, y2_p = person_box
                area_p = max(0, x2_p - x1_p) * max(0, y2_p - y1_p)
                w_p = max(0, x2_p - x1_p)
                h_p = max(0, y2_p - y1_p)
                
                if area_p == 0:
                    continue
                    
                is_rider = False
                track_id = int(track_ids[i])
                
                # 1. Kiểm tra hình học chồng lấn với tất cả phương tiện
                for v_idx in vehicle_indices:
                    v_box = boxes[v_idx]
                    x1_v, y1_v, x2_v, y2_v = v_box
                    
                    # Tính phần diện tích giao nhau
                    xx1 = max(x1_p, x1_v)
                    yy1 = max(y1_p, y1_v)
                    xx2 = min(x2_p, x2_v)
                    yy2 = min(y2_p, y2_v)
                    
                    w_inter = max(0, xx2 - xx1)
                    h_inter = max(0, yy2 - yy1)
                    inter_area = w_inter * h_inter
                    
                    # Điều kiện A: Đè diện tích > 30%
                    if (inter_area / area_p) > config.CONTAINMENT_THRESHOLD:
                        is_rider = True
                        break
                        
                    # Điều kiện B: Xếp chồng dọc (áp dụng đặc biệt cho xe máy 3 và xe đạp 1)
                    if class_ids[v_idx] in [1, 3]:
                        w_v = max(0, x2_v - x1_v)
                        # Độ trùng lấn ngang (Horizontal Overlap Ratio)
                        h_overlap = max(0, min(x2_p, x2_v) - max(x1_p, x1_v)) / min(w_p, w_v) if min(w_p, w_v) > 0 else 0
                        # Khoảng cách dọc (Vertical Gap) từ chân người tới đầu xe
                        v_gap = y1_v - y2_p
                        v_gap_ratio = v_gap / h_p if h_p > 0 else 999
                        
                        if h_overlap > 0.60 and v_gap_ratio < 0.15:
                            is_rider = True
                            break
                
                # 2. Kiểm tra bộ nhớ Temporal Rider
                if is_rider:
                    if track_id >= 0:
                        self.rider_tracks[track_id] = 0 # reset bộ nhớ đệm
                else:
                    # Nếu hình học không khớp ở frame này, kiểm tra xem trước đó có phải Rider không
                    if track_id >= 0 and track_id in self.rider_tracks:
                        if self.rider_tracks[track_id] < config.MAX_RIDER_MEMORY_FRAMES:
                            self.rider_tracks[track_id] += 1
                            is_rider = True
                        else:
                            # Quá 15 frame không gặp lại xe máy -> xóa khỏi bộ nhớ
                            del self.rider_tracks[track_id]
                            
                if not is_rider:
                    keep_indices.append(i)
                    
        # Dọn dẹp bộ nhớ đệm cho các track_id không còn xuất hiện trong frame hiện tại để tránh rò rỉ bộ nhớ
        current_person_tracks = {int(track_ids[idx]) for idx in person_indices if int(track_ids[idx]) >= 0}
        for tid in list(self.rider_tracks.keys()):
            if tid not in current_person_tracks:
                self.rider_tracks[tid] += 1
                if self.rider_tracks[tid] > config.MAX_RIDER_MEMORY_FRAMES * 2:
                    del self.rider_tracks[tid]
                    
        return keep_indices

    def filter_ego_car_hood(self, boxes, class_ids, track_ids, h, w):
        """
        Lọc bỏ Bounding Box của mui xe của chính mình (Self-car hood) ở cạnh dưới màn hình.
        Điều kiện:
        - Box rất rộng: width > 0.75 * w
        - Nằm sát đáy và phần dưới: y2 > 0.95 * h và y1 > 0.70 * h
        """
        keep_indices = []
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            width = x2 - x1
            
            # Kiểm tra nếu là mui xe tự thân
            is_hood = (width > 0.75 * w) and (y2 > 0.95 * h) and (y1 > 0.70 * h)
            
            if not is_hood:
                keep_indices.append(i)
        return keep_indices

    def filter_outside_lane(self, boxes, class_ids, track_ids, h, w):
        """
        Lọc bỏ những đối tượng nằm ngoài biên làn đường (trên vỉa hè).
        """
        keep_indices = []
        
        horizon_y = config.HORIZON_Y_PCT * h
        xl_bot = (0.5 - config.LANE_WIDTH_BOTTOM_PCT / 2) * w
        xr_bot = (0.5 + config.LANE_WIDTH_BOTTOM_PCT / 2) * w
        xl_top = (0.5 - config.LANE_WIDTH_TOP_PCT / 2) * w
        xr_top = (0.5 + config.LANE_WIDTH_TOP_PCT / 2) * w
        
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            cx = (x1 + x2) / 2
            
            # Tính toán vị trí biên làn tại y2 của vật thể
            t = (y2 - horizon_y) / (h - horizon_y) if h != horizon_y else 0
            t = max(0.0, min(1.0, t))
            
            xl = xl_top + t * (xl_bot - xl_top)
            xr = xr_top + t * (xr_bot - xr_top)
            
            # Thêm dung sai đè vạch 5% độ rộng làn tại điểm đó để tránh loại bỏ quá chặt
            lane_w = xr - xl
            tolerance = 0.05 * lane_w
            
            if (xl - tolerance) <= cx <= (xr + tolerance):
                keep_indices.append(i)
                
        return keep_indices

