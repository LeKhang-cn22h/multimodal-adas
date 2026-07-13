from fastapi import FastAPI
import uvicorn
import os

app = FastAPI(title="Vehicle Detection Service", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "vehicle-service"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8004"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
