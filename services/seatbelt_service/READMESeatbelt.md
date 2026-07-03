# Seatbelt Detection Service

YOLO-based seatbelt detection microservice. Fetches frames from camera-service
and runs inference on demand.

## Responsibility

- Load trained YOLO model (`best.pt`) at startup
- Fetch JPEG frames from camera-service via HTTP
- Run seatbelt detection (class 6) + auxiliary classes (phone, drinking, etc.)
- Track consecutive frames without seatbelt → warning state

## Endpoints

| Method | Path      | Returns                | Description                          |
|--------|-----------|------------------------|--------------------------------------|
| GET    | `/health` | `HealthResponse`       | Service + model + camera status      |
| GET    | `/check`  | `SeatbeltCheckResponse`| Run detection on latest camera frame |
| GET    | `/stats`  | `StatsResponse`        | Aggregated detection statistics      |

## Detection Classes

| ID | Class       |
|----|-------------|
| 0  | cell phone  |
| 1  | drinking    |
| 2  | eyeglass    |
| 3  | hands off   |
| 4  | hands on    |
| 5  | mask        |
| 6  | seatbelt    |

## Environment Variables

| Variable              | Default                          | Description                    |
|-----------------------|----------------------------------|--------------------------------|
| `CAMERA_SERVICE_URL`  | `http://camera-service:8005`     | Camera frame source            |
| `MODEL_PATH`          | `best.pt`                        | YOLO model file                |
| `CONFIDENCE_THRESHOLD`| 0.3                              | Minimum detection confidence   |
| `WARNING_FRAMES`      | 10                               | Frames without seatbelt → warn |
| `POLL_INTERVAL`       | 3.0                              | Suggested poll interval (sec)  |
| `PORT`                | 8002                             | HTTP listen port               |
| `LOG_LEVEL`           | INFO                             | Logging level                  |

## Usage

```bash
cd services/seatbelt_service
pip install -r requirements.txt
python main.py
```

Call from other services:

```
GET http://seatbelt-service:8002/check
```
