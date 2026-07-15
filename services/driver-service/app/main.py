from fastapi import FastAPI
import uvicorn
import os

app = FastAPI(title="Driver Monitoring Service", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "driver-service"}

<<<<<<< HEAD

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Driver Service")

    orchestrator = get_orchestrator()

    try:
        orchestrator.start()
        logger.info("Driver Service Ready")
        yield

    finally:
        logger.info("Stopping Driver Service")
        orchestrator.stop()


app = FastAPI(
    title="Driver Monitoring Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(fatigue_router)
=======
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
>>>>>>> origin/lane-vehicle_service
