import os

class Settings:
    """Tập hợp cấu hình của Lane Detection Service."""
    PORT = int(os.getenv("PORT", "8002"))
    
    # YOLO Settings
    YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolo11n.pt")
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))
    
    # Traffic Sign YOLO Settings
    TRAFFIC_SIGN_MODEL_PATH = os.getenv("TRAFFIC_SIGN_MODEL_PATH", r"E:\.rover-rasberry\voice\multimodal-adas\traffic-sign-yolo11n-classes_en.pt")
    TRAFFIC_SIGN_CONF_THRESHOLD = float(os.getenv("TRAFFIC_SIGN_CONF_THRESHOLD", "0.45"))
    
    # Processing limit
    MAX_FRAMES = int(os.getenv("MAX_FRAMES", "30"))

    # Camera Service Integration
    CAMERA_SERVICE_URL = os.getenv("CAMERA_SERVICE_URL", "http://localhost:8005/frame")

settings = Settings()

