# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cấu hình AI
MODEL_PATH = os.path.join(BASE_DIR, "yolo11s.pt") # Nâng cấp từ yolo11n lên yolo11s để tăng độ nhạy
TRACKER_CONFIG = os.path.join(BASE_DIR, "custom_bytetrack.yaml")
CONFIDENCE_THRESHOLD = 0.15 # Ngưỡng tin cậy (nhỏ hơn sẽ nhận diện được nhiều vật thể mờ/xa hơn)
CONTAINMENT_THRESHOLD = 0.30 # Ngưỡng 30% để lọc người ngồi trên xe/trong ô tô
MAX_RIDER_MEMORY_FRAMES = 15 # Bộ nhớ đệm 15 frame để tránh chập chờn nhãn người đi bộ

# Lớp đối tượng mục tiêu (COCO IDs: 0-person, 1-bicycle, 2-car, 3-motorcycle, 5-bus, 7-truck)
TARGET_CLASSES = [0, 1, 2, 3, 5, 7]
CLASS_NAMES = {
    0: 'Nguoi di bo',
    1: 'Bicyclist',
    2: 'Xe hoi',
    3: 'Motorcyclist',
    5: 'Xe buyt',
    7: 'Xe tai'
}

# Cấu hình Vùng Không Gian (Spatial Danger Grading)
# Khoảng cách mô phỏng (mét)
DANGER_ZONE_DISTANCE = 8.0
WARNING_ZONE_DISTANCE = 22.0
HORIZON_Y_PCT = 0.45
LANE_WIDTH_BOTTOM_PCT = 0.90
LANE_WIDTH_TOP_PCT = 0.30

# Màu sắc Bounding Box (BGR)
COLOR_DANGER = (0, 0, 255)     # Đỏ
COLOR_WARNING = (0, 255, 255)  # Vàng
COLOR_SAFE = (0, 255, 0)       # Xanh lá

# Cấu hình Audio Queue
AUDIO_PRIORITY_DANGER = 1
AUDIO_PRIORITY_WARNING_PEDESTRIAN = 2
AUDIO_PRIORITY_WARNING_VEHICLE = 3
