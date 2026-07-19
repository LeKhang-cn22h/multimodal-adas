from ultralytics import YOLO
from config import settings as config

class ObjectDetector:
    """
    Module for AI model inference (YOLOv11s + ByteTrack).
    """
    def __init__(self):
        # Load YOLO model from configuration path (defaults to yolo11s.pt)
        self.model = YOLO(config.YOLO_MODEL_PATH)
        self.target_classes = getattr(config, "TARGET_CLASSES", [0, 1, 2, 3, 5, 7])
        self.tracker_config = getattr(config, "TRACKER_CONFIG", "bytetrack.yaml")
        self.rider_tracks = {} # track_id -> frames_since_last_overlap

    def track_objects(self, frame):
        """
        Run YOLOv11 and ByteTrack on optimized ROI.
        Crops top 35% (sky) and bottom 10% (car hood) to optimize CPU and prevent false positives.
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
        
        # Map crop coordinates back to original frame
        if result.boxes is not None and len(result.boxes) > 0:
            # Clone data to prevent PyTorch inplace update errors
            new_data = result.boxes.data.clone()
            new_data[:, 1] += y_start # y1
            new_data[:, 3] += y_start # y2
            result.boxes.data = new_data
            
        # Reassign original image and shape for proper distance estimation downstream
        result.orig_img = frame
        result.orig_shape = (h, w)
        
        return result

    def predict_objects(self, frame):
        """
        Run YOLOv11 in prediction mode (static image) on optimized ROI.
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
        Filters out nested/parasite bounding boxes (nested objects) inside large vehicles.
        Removes ghost detections on vehicle rears.
        """
        keep_indices = []
        
        # Vulnerable classes: Person (0), Bicycle (1), Motorcycle (3)
        vulnerable_indices = [i for i, cls in enumerate(class_ids) if cls in [0, 1, 3]]
        # Large vehicle classes: Car (2), Bus (5), Truck (7)
        large_vehicle_indices = [i for i, cls in enumerate(class_ids) if cls in [2, 5, 7]]
        
        for i in range(len(boxes)):
            if i not in vulnerable_indices:
                # Keep large vehicles automatically
                keep_indices.append(i)
            else:
                vul_box = boxes[i]
                x1_v, y1_v, x2_v, y2_v = vul_box
                area_v = max(0, x2_v - x1_v) * max(0, y2_v - y1_v)
                
                if area_v == 0:
                    continue
                    
                is_parasite = False
                track_id = int(track_ids[i])
                
                # Check overlapping area with all large vehicles
                for l_idx in large_vehicle_indices:
                    l_box = boxes[l_idx]
                    x1_l, y1_l, x2_l, y2_l = l_box
                    
                    # Calculate intersection coordinates
                    xx1 = max(x1_v, x1_l)
                    yy1 = max(y1_v, y1_l)
                    xx2 = min(x2_v, x2_l)
                    yy2 = min(y2_v, y2_l)
                    
                    w_inter = max(0, xx2 - xx1)
                    h_inter = max(0, yy2 - yy1)
                    inter_area = w_inter * h_inter
                    
                    # If containment exceeds threshold (default 30%)
                    containment_thresh = getattr(config, "CONTAINMENT_THRESHOLD", 0.3)
                    if (inter_area / area_v) > containment_thresh:
                        is_parasite = True
                        break
                        
                # Handle temporal riders
                max_rider_mem = getattr(config, "MAX_RIDER_MEMORY_FRAMES", 10)
                if is_parasite:
                    if track_id >= 0:
                        self.rider_tracks[track_id] = 0
                else:
                    if track_id >= 0 and track_id in self.rider_tracks:
                        if self.rider_tracks[track_id] < max_rider_mem:
                            self.rider_tracks[track_id] += 1
                            is_parasite = True
                        else:
                            del self.rider_tracks[track_id]
                            
                if not is_parasite:
                    keep_indices.append(i)
                    
        # Cleanup cached memory
        current_vul_tracks = {int(track_ids[idx]) for idx in vulnerable_indices if int(track_ids[idx]) >= 0}
        for tid in list(self.rider_tracks.keys()):
            if tid not in current_vul_tracks:
                self.rider_tracks[tid] += 1
                if self.rider_tracks[tid] > max_rider_mem * 2:
                    del self.rider_tracks[tid]
                    
        return keep_indices

    def filter_ego_car_hood(self, boxes, class_ids, track_ids, h, w):
        """
        Filters out self-car hood bounding boxes at the bottom edge.
        Conditions:
        - Box is wide: width > 0.75 * w
        - Located near bottom: y2 > 0.95 * h and y1 > 0.70 * h
        """
        keep_indices = []
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            width = x2 - x1
            
            is_hood = (width > 0.75 * w) and (y2 > 0.95 * h) and (y1 > 0.70 * h)
            
            if not is_hood:
                keep_indices.append(i)
        return keep_indices

    def filter_outside_lane(self, boxes, class_ids, track_ids, h, w):
        """
        Filters out ghost boxes based on area and aspect ratio logic.
        """
        keep_indices = []
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
            area = width * height
            cls_id = class_ids[i]
            
            # Filter out very small boxes for large vehicles
            if cls_id in [2, 5, 7] and area < (w * h * 0.001):
                continue
                
            aspect_ratio = width / height
            
            # Pedestrians stand vertically (ratio usually < 1.2)
            if cls_id == 0 and aspect_ratio > 1.2:
                continue
                
            # Motorcycles/Bicycles range
            if cls_id in [1, 3] and (aspect_ratio > 2.0 or aspect_ratio < 0.35):
                continue
                
            # Cars, trucks, buses are wider than high
            if cls_id in [2, 5, 7] and (aspect_ratio > 5.0 or aspect_ratio < 0.35):
                continue
                
            keep_indices.append(i)
        return keep_indices
