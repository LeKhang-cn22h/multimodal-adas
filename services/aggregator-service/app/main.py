"""
aggregator-service
------------------
Thu thập events từ tất cả services (driver, lane, vehicle, camera),
tổng hợp và expose REST API cho API Gateway + Dashboard.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import time
import collections
import uvicorn
import os

app = FastAPI(title="ADAS Aggregator Service", version="1.0.0")

# ==========================
# In-memory event store
# Trong production: thay bằng Redis
# ==========================
MAX_EVENTS = 1000
events: collections.deque = collections.deque(maxlen=MAX_EVENTS)

# Alert level priority
PRIORITY = {"AWAKE": 0, "TIRED": 1, "DROWSY": 2, "DANGEROUS": 3}

# ==========================
# Schemas
# ==========================
class EventIn(BaseModel):
    source: str                     # "driver-service" | "lane-service" | ...
    alert_level: str                # "AWAKE" | "TIRED" | "DROWSY" | "DANGEROUS"
    timestamp: Optional[float] = None
    # Extra fields từ mỗi service
    ear: Optional[float] = None
    lane_offset: Optional[float] = None
    vehicle_distance: Optional[float] = None
    data: Optional[dict] = None

class SystemStatus(BaseModel):
    overall_alert: str
    active_services: list[str]
    event_count: int
    last_updated: float

# ==========================
# Routes
# ==========================
@app.get("/health")
def health():
    return {"status": "ok", "service": "aggregator"}

@app.post("/event", status_code=201)
def receive_event(event: EventIn):
    """Nhận event từ bất kỳ service nào."""
    record = event.dict()
    record["received_at"] = time.time()
    if not record.get("timestamp"):
        record["timestamp"] = record["received_at"]
    events.append(record)
    return {"ok": True}

@app.get("/events")
def get_events(limit: int = 50, source: Optional[str] = None):
    """Lấy events gần nhất, có thể filter theo source."""
    result = list(reversed(events))  # mới nhất trước
    if source:
        result = [e for e in result if e["source"] == source]
    return result[:limit]

@app.get("/status", response_model=SystemStatus)
def get_status():
    """Trả về trạng thái tổng hợp toàn hệ thống."""
    if not events:
        return SystemStatus(
            overall_alert="AWAKE",
            active_services=[],
            event_count=0,
            last_updated=time.time(),
        )

    # Lấy events trong 5 giây gần nhất
    now = time.time()
    recent = [e for e in events if now - e.get("received_at", 0) < 5.0]

    # Overall alert = level cao nhất trong recent events
    overall = "AWAKE"
    for e in recent:
        lvl = e.get("alert_level", "AWAKE")
        if PRIORITY.get(lvl, 0) > PRIORITY.get(overall, 0):
            overall = lvl

    active = list({e["source"] for e in recent})

    return SystemStatus(
        overall_alert=overall,
        active_services=active,
        event_count=len(events),
        last_updated=now,
    )

@app.get("/stats")
def get_stats():
    """Thống kê phân bố alert levels."""
    counts: dict[str, int] = {"AWAKE": 0, "TIRED": 0, "DROWSY": 0, "DANGEROUS": 0}
    sources: dict[str, int] = {}
    for e in events:
        lvl = e.get("alert_level", "AWAKE")
        counts[lvl] = counts.get(lvl, 0) + 1
        src = e.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    return {"alert_counts": counts, "by_source": sources, "total": len(events)}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8003"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)