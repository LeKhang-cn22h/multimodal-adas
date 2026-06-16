from fastapi import FastAPI
import uvicorn
import os

app = FastAPI(title="Camera Management Service", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "camera-service"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8005"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
