from ultralytics import YOLO
import config

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
        Chạy mô hình YOLOv11 để nhận diện và ByteTrack để theo dõi trên vùng ROI tối ưu.
        Cắt bỏ phần bầu trời (trên 35%) và nắp capo (dưới 10%) để giảm tải CPU và tránh báo động giả.
        """
        h, w = frame.shape[:2]
        y_start = int(0.35 * h)
        y_end = int(0.90 * h)
        
        cropped_frame = frame[y_start:y_end, :]
        
        results = self.model.track(
            cropped_frame, 
            persist=True, 
            tracker=self.tracker_config, 
            classes=self.target_classes, 
            conf=config.CONFIDENCE_THRESHOLD,
            verbose=False
        )
        
        result = results[0]
        
        # Ánh xạ tọa độ từ ảnh cropped về ảnh gốc
        if result.boxes is not None and len(result.boxes) > 0:
            # Clone dữ liệu để tránh lỗi "Inplace update to inference tensor" của PyTorch
            new_data = result.boxes.data.clone()
            new_data[:, 1] += y_start # y1
            new_data[:, 3] += y_start # y2
            result.boxes.data = new_data
            
        # Gán lại ảnh gốc và kích thước gốc để các module sau hiển thị/tính toán khoảng cách đúng
        result.orig_img = frame
        result.orig_shape = (h, w)
        
        return result

    def predict_objects(self, frame):
        """
        Chạy mô hình YOLOv11 ở chế độ nhận diện (predict) cho ảnh tĩnh trên vùng ROI tối ưu.
        """
        h, w = frame.shape[:2]
        y_start = int(0.35 * h)
        y_end = int(0.90 * h)
        
        cropped_frame = frame[y_start:y_end, :]
        
        results = self.model.predict(
            cropped_frame, 
            classes=self.target_classes, 
            conf=config.CONFIDENCE_THRESHOLD,
            verbose=False
        )
        
        result = results[0]
        
        if result.boxes is not None and len(result.boxes) > 0:
            new_data = result.boxes.data.clone()
            new_data[:, 1] += y_start # y1
            new_data[:, 3] += y_start # y2
            result.boxes.data = new_data
            
        result.orig_img = frame
        result.orig_shape = (h, w)
        
        return result

    def filter_inside_vehicles(self, boxes, class_ids, track_ids):
        """
        Lọc bỏ Bounding Box ký sinh (Nested Objects) nếu nằm > 30% bên trong phương tiện lớn.
        Đặc biệt hiệu quả để xóa các bóng ma xe máy/người trên đuôi xe hơi.
        """
        keep_indices = []
        
        # Nhóm "Ký sinh": Người (0), Xe đạp (1), Xe máy (3)
        vulnerable_indices = [i for i, cls in enumerate(class_ids) if cls in [0, 1, 3]]
        # Nhóm "Vật chủ" (Phương tiện to): Xe hơi (2), Bus (5), Tải (7)
        large_vehicle_indices = [i for i, cls in enumerate(class_ids) if cls in [2, 5, 7]]
        
        for i in range(len(boxes)):
            if i not in vulnerable_indices:
                # Giữ lại toàn bộ các vật thể lớn (Xe hơi, tải, buýt, v.v.)
                keep_indices.append(i)
            else:
                vul_box = boxes[i]
                x1_v, y1_v, x2_v, y2_v = vul_box
                area_v = max(0, x2_v - x1_v) * max(0, y2_v - y1_v)
                
                if area_v == 0:
                    continue
                    
                is_parasite = False
                track_id = int(track_ids[i])
                
                # Kiểm tra hình học chồng lấn với tất cả phương tiện lớn
                for l_idx in large_vehicle_indices:
                    l_box = boxes[l_idx]
                    x1_l, y1_l, x2_l, y2_l = l_box
                    
                    # Tính phần diện tích giao nhau
                    xx1 = max(x1_v, x1_l)
                    yy1 = max(y1_v, y1_l)
                    xx2 = min(x2_v, x2_l)
                    yy2 = min(y2_v, y2_l)
                    
                    w_inter = max(0, xx2 - xx1)
                    h_inter = max(0, yy2 - yy1)
                    inter_area = w_inter * h_inter
                    
                    # Nếu > 30% diện tích của xe máy/người nằm gọn trong xe hơi
                    if (inter_area / area_v) > config.CONTAINMENT_THRESHOLD:
                        is_parasite = True
                        break
                        
                # Xử lý Temporal Rider (Nếu trước đây nó là xe máy thật, có thể nó bị che khuất tạm thời)
                if is_parasite:
                    if track_id >= 0:
                        self.rider_tracks[track_id] = 0
                else:
                    if track_id >= 0 and track_id in self.rider_tracks:
                        if self.rider_tracks[track_id] < config.MAX_RIDER_MEMORY_FRAMES:
                            self.rider_tracks[track_id] += 1
                            is_parasite = True
                        else:
                            del self.rider_tracks[track_id]
                            
                if not is_parasite:
                    keep_indices.append(i)
                    
        # Dọn dẹp bộ nhớ đệm
        current_vul_tracks = {int(track_ids[idx]) for idx in vulnerable_indices if int(track_ids[idx]) >= 0}
        for tid in list(self.rider_tracks.keys()):
            if tid not in current_vul_tracks:
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
        Lọc bỏ nhiễu/bóng ma (Ghost Frames) dựa trên diện tích và kỷ luật tỷ lệ khung hình (Aspect Ratio).
        """
        keep_indices = []
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
            area = width * height
            cls_id = class_ids[i]
            
            # 1. Lọc nhiễu đốm sáng quá nhỏ (Chỉ áp dụng cho Xe hơi 2, Buýt 5, Tải 7)
            if cls_id in [2, 5, 7] and area < (w * h * 0.001):
                continue
                
            # 2. Kỷ luật tỷ lệ khung hình nghiêm ngặt (Aspect Ratio = Width / Height)
            aspect_ratio = width / height
            
            # Người đi bộ (0) thường đứng thẳng, cao hơn rộng (ratio thường < 1.0)
            if cls_id == 0 and aspect_ratio > 1.2:
                continue
                
            # Xe máy/Xe đạp (1, 3) hiếm khi quá rộng hoặc quá cao hẹp
            if cls_id in [1, 3] and (aspect_ratio > 2.0 or aspect_ratio < 0.35):
                continue
                
            # Ô tô, tải, buýt (2, 5, 7) thường rộng hơn cao (ratio > 0.8), ngoại trừ khi nhìn từ xa thẳng
            if cls_id in [2, 5, 7] and (aspect_ratio > 5.0 or aspect_ratio < 0.35):
                continue
                
            keep_indices.append(i)
        return keep_indices

