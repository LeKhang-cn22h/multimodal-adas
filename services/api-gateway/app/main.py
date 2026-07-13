"""
api-gateway
-----------
Chạy trên máy mạnh nhất.
Nhận requests từ dashboard/client, route đến đúng service.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import uvicorn

app = FastAPI(title="ADAS API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Production: giới hạn lại domain dashboard
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Service URLs (từ env vars)
# ==========================
SERVICES = {
    "driver":      os.getenv("DRIVER_SERVICE_URL",      "http://driver-service:8001"),
    "lane":        os.getenv("LANE_SERVICE_URL",         "http://lane-service:8002"),
    "vehicle":     os.getenv("VEHICLE_SERVICE_URL",      "http://vehicle-service:8004"),
    "camera":      os.getenv("CAMERA_SERVICE_URL",       "http://camera-service:8005"),
    "aggregator":  os.getenv("AGGREGATOR_SERVICE_URL",   "http://aggregator-service:8003"),
}

TIMEOUT = httpx.Timeout(5.0)

# ==========================
# Health check
# ==========================
@app.get("/health")
def health():
    return {"status": "ok", "service": "api-gateway"}

@app.get("/services/health")
async def check_all_services():
    """Ping tất cả services và trả về trạng thái."""
    results = {}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for name, url in SERVICES.items():
            try:
                r = await client.get(f"{url}/health")
                results[name] = {"status": "up", "code": r.status_code}
            except Exception as e:
                results[name] = {"status": "down", "error": str(e)}
    return results

# ==========================
# Proxy routes → aggregator
# ==========================
@app.get("/api/status")
async def get_system_status():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{SERVICES['aggregator']}/status")
            return r.json()
        except Exception as e:
            raise HTTPException(502, f"Aggregator unreachable: {e}")

@app.get("/api/events")
async def get_events(limit: int = 50, source: str = None):
    params = {"limit": limit}
    if source:
        params["source"] = source
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{SERVICES['aggregator']}/events", params=params)
            return r.json()
        except Exception as e:
            raise HTTPException(502, f"Aggregator unreachable: {e}")

@app.get("/api/stats")
async def get_stats():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{SERVICES['aggregator']}/stats")
            return r.json()
        except Exception as e:
            raise HTTPException(502, f"Aggregator unreachable: {e}")

# ==========================
# Generic proxy (bất kỳ service nào)
# ==========================
@app.api_route("/proxy/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(service: str, path: str, request: Request):
    """
    Generic proxy: /proxy/driver/health → driver-service/health
    Dùng để gọi bất kỳ endpoint nào trên bất kỳ service nào.
    """
    if service not in SERVICES:
        raise HTTPException(404, f"Service '{service}' không tồn tại")

    url = f"{SERVICES[service]}/{path}"
    body = await request.body()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
            )
            return r.json()
        except Exception as e:
            raise HTTPException(502, f"Service '{service}' unreachable: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)