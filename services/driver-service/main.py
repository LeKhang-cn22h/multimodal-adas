import uvicorn
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )