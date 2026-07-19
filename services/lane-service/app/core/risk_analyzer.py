import numpy as np
from config import settings as config

class RiskAnalyzer:
    """
    Rule-based safety collision risk analyzer module using temporal features.
    """
    def __init__(self):
        # Keep track history to calculate growth rate and persistence
        # Format: {track_id: {"last_area": float, "growth_rate": float, "persistence": int, "last_frame_id": int}}
        self.history = {}

    @staticmethod
    def estimate_distance(bbox, frame_height):
        """
        Estimate physical distance (meters) based on Inverse Perspective Mapping (IPM).
        """
        _, _, _, y2 = bbox
        horizon_y = getattr(config, "HORIZON_Y_PCT", 0.35) * frame_height
        
        # Prevent division by zero and negative distances
        y_diff = max(1, y2 - horizon_y)
        distance = (3.0 * frame_height) / y_diff
        return min(100.0, max(2.0, distance))

    def analyze_frame(self, frame, boxes, class_ids, track_ids, confidences, frame_id):
        """
        Analyze the full frame and output hazard metrics for objects and global warnings.
        """
        h, w = frame.shape[:2]
        
        # 1. Edge Case Checks: Camera occlusion or glare
        camera_occluded = False
        camera_status_msg = None
        mean_val = np.mean(frame)
        std_val = np.std(frame)
        
        if mean_val < 10:
            camera_occluded = True
            camera_status_msg = "Cảnh báo: Camera bị che khuất hoàn toàn (Quá tối)!"
        elif mean_val > 245:
            camera_occluded = True
            camera_status_msg = "Cảnh báo: Camera bị chói sáng nghiêm trọng!"
        elif std_val < 5:
            camera_occluded = True
            camera_status_msg = "Cảnh báo: Camera bị che khuất (Ảnh đồng nhất)!"

        processed_objects = []
        high_risk_count = 0
        
        # Mapping COCO IDs to English class names
        coco_to_english = {
            0: "person",
            1: "bicyclist",
            2: "car",
            3: "motorcyclist",
            5: "bus",
            7: "truck"
        }

        # Clear stale history entries (not seen for > 100 frames)
        for t_id in list(self.history.keys()):
            if frame_id - self.history[t_id]["last_frame_id"] > 100:
                del self.history[t_id]

        for box, track_id, class_id, conf in zip(boxes, track_ids, class_ids, confidences):
            x1, y1, x2, y2 = box
            area = (x2 - x1) * (y2 - y1)
            center_x = (x1 + x2) / 2
            
            # Estimate horizontal position
            if center_x < w / 3:
                position = "front_left"
            elif center_x > 2 * w / 3:
                position = "front_right"
            else:
                position = "front_center"

            # Update temporal features (growth rate & persistence)
            if track_id in self.history and frame_id - self.history[track_id]["last_frame_id"] == 1:
                prev_area = self.history[track_id]["last_area"]
                growth_rate = (area - prev_area) / prev_area if prev_area > 0 else 0.0
                persistence = self.history[track_id]["persistence"] + 1
            else:
                growth_rate = 0.0
                persistence = 1

            self.history[track_id] = {
                "last_area": area,
                "growth_rate": growth_rate,
                "persistence": persistence,
                "last_frame_id": frame_id
            }

            # Estimate distance
            distance = self.estimate_distance(box, h)

            # Rule evaluation
            risk_level = "low"
            alert_message = None
            color = getattr(config, "COLOR_SAFE", "green")
            priority = None

            # Extremely close objects
            if y2 > 0.95 * h or (area / (w * h)) > 0.30:
                risk_level = "high"
                alert_message = "Chú ý! Phương tiện phía trước quá gần!"
                color = getattr(config, "COLOR_DANGER", "red")
                priority = getattr(config, "AUDIO_PRIORITY_DANGER", 1)

            # Danger Zone
            elif distance <= getattr(config, "DANGER_ZONE_DISTANCE", 2.5):
                if class_id == 0:  # Pedestrian
                    if persistence >= 3: # Frame noise filter
                        risk_level = "high"
                        alert_message = "Phát hiện người đi bộ phía trước."
                        color = getattr(config, "COLOR_DANGER", "red")
                        priority = getattr(config, "AUDIO_PRIORITY_DANGER", 1)
                else:  # Vehicles
                    if growth_rate > 0.02:
                        risk_level = "high"
                        alert_message = "Phương tiện phía trước quá gần!"
                        color = getattr(config, "COLOR_DANGER", "red")
                        priority = getattr(config, "AUDIO_PRIORITY_DANGER", 1)
                    else:
                        risk_level = "medium"
                        class_names = getattr(config, "CLASS_NAMES", {})
                        class_name_vn = class_names.get(int(class_id), "vật thể")
                        if int(class_id) == 3:
                            alert_name = "người lái xe máy"
                        elif int(class_id) == 1:
                            alert_name = "người lái xe đạp"
                        else:
                            alert_name = class_name_vn.lower()
                        alert_message = f"Phát hiện {alert_name} phía trước."
                        color = getattr(config, "COLOR_WARNING", "orange")
                        priority = getattr(config, "AUDIO_PRIORITY_WARNING_VEHICLE", 2)

            # Warning Zone
            elif distance <= getattr(config, "WARNING_ZONE_DISTANCE", 7.0):
                if class_id in [0, 1, 3]:  # Pedestrians/Two-wheelers heading closer
                    if growth_rate > 0.0:
                        risk_level = "medium"
                        alert_message = "Chú ý đối tượng phía trước."
                        color = getattr(config, "COLOR_WARNING", "orange")
                        priority = getattr(config, "AUDIO_PRIORITY_WARNING_PEDESTRIAN", 3) if class_id == 0 else getattr(config, "AUDIO_PRIORITY_WARNING_VEHICLE", 2)
            
            if risk_level == "high":
                high_risk_count += 1

            processed_objects.append({
                "track_id": int(track_id),
                "class_name": coco_to_english.get(int(class_id), "unknown"),
                "confidence": float(conf),
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "position": position,
                "risk_level": risk_level,
                "alert_message": alert_message,
                "distance": round(distance, 1),
                "color": color,
                "priority": priority
            })

        # Global Frame Risk assessment
        global_risk_level = "low"
        global_alert_msg = None
        global_priority = None

        if high_risk_count >= 2:
            global_risk_level = "critical"
            global_alert_msg = "Cảnh báo nguy hiểm phía trước. Vui lòng giảm tốc độ."
            global_priority = getattr(config, "AUDIO_PRIORITY_DANGER", 1)
        elif high_risk_count == 1:
            global_risk_level = "high"
            high_risk_objs = [o for o in processed_objects if o["risk_level"] == "high"]
            global_alert_msg = high_risk_objs[0]["alert_message"]
            global_priority = high_risk_objs[0]["priority"]
        else:
            medium_objs = [o for o in processed_objects if o["risk_level"] == "medium"]
            if len(medium_objs) > 0:
                global_risk_level = "medium"
                global_alert_msg = medium_objs[0]["alert_message"]
                global_priority = medium_objs[0]["priority"]

        return {
            "camera_occluded": camera_occluded,
            "camera_status_msg": camera_status_msg,
            "global_risk_level": global_risk_level,
            "global_alert_msg": global_alert_msg,
            "global_priority": global_priority,
            "objects": processed_objects
        }
