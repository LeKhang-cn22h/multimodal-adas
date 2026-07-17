import os

class Settings:
    """Tập hợp cấu hình của Lane Detection Service."""
    PORT = int(os.getenv("PORT", "8002"))
    
    BASE_DIR =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # YOLO Settings
    YOLO_MODEL_PATH = os.path.join(BASE_DIR, "models", os.getenv("YOLO_MODEL_PATH", "yolo11n.pt"))
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))
    TARGET_CLASSES = [0, 1, 2, 3, 5, 7] # person, bicycle, car, motorcycle, bus, truck
    TRACKER_CONFIG = "bytetrack.yaml"
    CONTAINMENT_THRESHOLD = 0.3
    MAX_RIDER_MEMORY_FRAMES = 10
    
    # Risk Assessment Parameters
    HORIZON_Y_PCT = 0.35
    DANGER_ZONE_DISTANCE = 2.5
    WARNING_ZONE_DISTANCE = 7.0
    SAFE_COOLDOWN_SECONDS = 5.0
    
    # Alert Priority & HUD colors
    COLOR_SAFE = "green"
    COLOR_WARNING = "orange"
    COLOR_DANGER = "red"
    AUDIO_PRIORITY_DANGER = 1
    AUDIO_PRIORITY_WARNING_VEHICLE = 2
    AUDIO_PRIORITY_WARNING_PEDESTRIAN = 3
    CLASS_NAMES = {0: "Người đi bộ", 1: "Xe đạp", 2: "Xe hơi", 3: "Xe máy", 5: "Xe buýt", 7: "Xe tải"}
    
    # RabbitMQ Settings
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
    RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "safety_signals")
    
    # UDP Stream Settings
    DASHBOARD_UDP_HOST = os.getenv("DASHBOARD_UDP_HOST", "127.0.0.1")
    DASHBOARD_UDP_PORT = int(os.getenv("DASHBOARD_UDP_PORT", "1236"))
    
    # Processing limit
    MAX_FRAMES = int(os.getenv("MAX_FRAMES", "30"))

    # Camera Service Integration
    CAMERA_SERVICE_URL = os.getenv("CAMERA_SERVICE_URL", "http://localhost:8005/frame")

settings = Settings()
