import os

class Settings:
    """Tập hợp cấu hình của Lane Detection Service."""
    PORT = int(os.getenv("PORT", "8002"))
    
    # YOLO Settings
    YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolo11n.pt")
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))
    
    # Processing limit
    MAX_FRAMES = int(os.getenv("MAX_FRAMES", "30"))

settings = Settings()
