import numpy as np
import config

class RiskAnalyzer:
    """
    Module phân tích nguy cơ dựa trên luật nghiệp vụ (Rule-based)
    và các đặc trưng temporal (BBox Growth Rate, Persistence, Center Alignment)
    """
    def __init__(self):
        # Lưu vết lịch sử của từng track_id để tính toán growth rate và persistence
        # Cấu trúc: {track_id: {"last_area": float, "growth_rate": float, "persistence": int, "last_frame_id": int}}
        self.history = {}

    @staticmethod
    def estimate_distance(bbox, frame_height):
        """
        Ước lượng khoảng cách (mét) dựa trên mô hình phối cảnh ngược (Inverse Perspective Mapping).
        """
        _, _, _, y2 = bbox
        horizon_y = config.HORIZON_Y_PCT * frame_height
        
        # Tránh chia cho 0 hoặc khoảng cách âm
        y_diff = max(1, y2 - horizon_y)
        distance = (3.0 * frame_height) / y_diff
        return min(100.0, max(2.0, distance))

    def analyze_frame(self, frame, boxes, class_ids, track_ids, confidences, frame_id):
        """
        Phân tích toàn bộ khung hình và đưa ra mức độ nguy hiểm chi tiết cho từng đối tượng
        và cảnh báo hệ thống.
        """
        h, w = frame.shape[:2]
        
        # 1. Kiểm tra Edge Cases: Camera bị che khuất hoặc chói sáng (EC02/EC03)
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
        
        # Dịch lớp COCO sang tiếng Anh cho đầu ra JSON tiêu chuẩn (Bản v3.2 mapping trực tiếp)
        coco_to_english = {
            0: "person",
            1: "bicyclist",
            2: "car",
            3: "motorcyclist",
            5: "bus",
            7: "truck"
        }

        # Dọn dẹp các track quá cũ trong history để tránh tràn bộ nhớ (lưu quá 100 frame không thấy)
        for t_id in list(self.history.keys()):
            if frame_id - self.history[t_id]["last_frame_id"] > 100:
                del self.history[t_id]

        for box, track_id, class_id, conf in zip(boxes, track_ids, class_ids, confidences):
            x1, y1, x2, y2 = box
            area = (x2 - x1) * (y2 - y1)
            center_x = (x1 + x2) / 2
            
            # Tính toán vị trí không gian (front_left, front_center, front_right)
            if center_x < w / 3:
                position = "front_left"
            elif center_x > 2 * w / 3:
                position = "front_right"
            else:
                position = "front_center"

            # Cập nhật thông tin Temporal Features (growth rate & persistence)
            if track_id in self.history and frame_id - self.history[track_id]["last_frame_id"] == 1:
                # Đối tượng tiếp tục xuất hiện liên tục
                prev_area = self.history[track_id]["last_area"]
                growth_rate = (area - prev_area) / prev_area if prev_area > 0 else 0.0
                persistence = self.history[track_id]["persistence"] + 1
            else:
                # Đối tượng mới xuất hiện hoặc mới được nhận diện lại
                growth_rate = 0.0
                persistence = 1

            self.history[track_id] = {
                "last_area": area,
                "growth_rate": growth_rate,
                "persistence": persistence,
                "last_frame_id": frame_id
            }

            # Ước lượng khoảng cách từ điểm đáy của bbox
            distance = self.estimate_distance(box, h)

            # Luật đánh giá nguy hiểm (Section 9.2 & EC23)
            risk_level = "low"
            alert_message = None
            color = config.COLOR_SAFE
            priority = None

            # EC23: Vật thể quá gần (Điểm đáy sát mép dưới > 95% hoặc chiếm > 30% diện tích màn hình)
            if y2 > 0.95 * h or (area / (w * h)) > 0.30:
                risk_level = "high"
                alert_message = "Chú ý! Phương tiện phía trước quá gần!"
                color = config.COLOR_DANGER
                priority = config.AUDIO_PRIORITY_DANGER

            # Vùng Nguy Hiểm (Danger Zone)
            elif distance <= config.DANGER_ZONE_DISTANCE:
                if class_id == 0:  # Người đi bộ
                    if persistence >= 3:  # Lọc nhiễu 1-2 frame
                        risk_level = "high"
                        alert_message = "Phát hiện người đi bộ phía trước."
                        color = config.COLOR_DANGER
                        priority = config.AUDIO_PRIORITY_DANGER
                else:  # Phương tiện giao thông
                    # Nếu đang tiến lại gần (diện tích tăng trưởng)
                    if growth_rate > 0.02:
                        risk_level = "high"
                        alert_message = "Phương tiện phía trước quá gần!"
                        color = config.COLOR_DANGER
                        priority = config.AUDIO_PRIORITY_DANGER
                    else:
                        risk_level = "medium"
                        class_name_vn = config.CLASS_NAMES.get(int(class_id), "vật thể")
                        # Ánh xạ thoại cảnh báo tự nhiên (tiếng Việt có dấu cho loa cảnh báo)
                        if int(class_id) == 3: # Motorcyclist
                            alert_name = "người lái xe máy"
                        elif int(class_id) == 1: # Bicyclist
                            alert_name = "người lái xe đạp"
                        else:
                            alert_name = class_name_vn.lower()
                        alert_message = f"Phát hiện {alert_name} phía trước."
                        color = config.COLOR_WARNING
                        priority = config.AUDIO_PRIORITY_WARNING_VEHICLE

            # Vùng Cảnh Báo (Warning Zone)
            elif distance <= config.WARNING_ZONE_DISTANCE:
                # Chỉ cảnh báo đối tượng cơ động yếu / dễ bị tổn thương (Người đi bộ, xe máy/motorcyclist, xe đạp/bicyclist) và đang tiến lại gần
                if class_id in [0, 1, 3]:  # Person, Bicyclist (1), Motorcyclist (3)
                    if growth_rate > 0.0:  # Có xu hướng tiến gần
                        risk_level = "medium"
                        alert_message = "Chú ý đối tượng phía trước."
                        color = config.COLOR_WARNING
                        priority = config.AUDIO_PRIORITY_WARNING_PEDESTRIAN if class_id == 0 else config.AUDIO_PRIORITY_WARNING_VEHICLE
            
            if risk_level == "high":
                high_risk_count += 1

            processed_objects.append({
                "track_id": int(track_id),
                "class": coco_to_english.get(int(class_id), "unknown"),
                "confidence": float(conf),
                "bbox_xyxy": [int(x1), int(y1), int(x2), int(y2)],
                "position": position,
                "risk_level": risk_level,
                "alert_message": alert_message,
                "distance": distance,
                "color": color,
                "priority": priority
            })

        # Đánh giá cảnh báo tổng thể (Global Frame Risk)
        global_risk_level = "low"
        global_alert_msg = None
        global_priority = None

        if high_risk_count >= 2:
            global_risk_level = "critical"
            global_alert_msg = "Cảnh báo nguy hiểm phía trước. Vui lòng giảm tốc độ."
            global_priority = config.AUDIO_PRIORITY_DANGER
        elif high_risk_count == 1:
            global_risk_level = "high"
            # Lấy thông điệp của vật thể high risk
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
