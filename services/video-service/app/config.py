import os

class Settings:
    """Cấu hình cho Video Service."""
    PORT = int(os.getenv("PORT", "8006"))
    
    # Thư mục lưu trữ video, mặc định nằm tại app/storage/
    STORAGE_DIR = os.getenv(
        "STORAGE_DIR", 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")
    )

settings = Settings()
