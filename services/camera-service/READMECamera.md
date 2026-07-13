# Camera Service

Manages the single webcam capture session for the ADAS system.
All other services obtain frames through this service's API.

## Responsibility

- Opens the laptop webcam **once** (sole owner of the camera device)
- Runs a background thread for continuous frame capture
- Pre-encodes every frame to JPEG in memory
- Serves frames to other services via HTTP

## Endpoints

| Method | Path       | Returns         | Description                        |
|--------|------------|------------------|------------------------------------|
| GET    | `/health`  | `HealthResponse` | Service + camera health status     |
| GET    | `/frame`   | `image/jpeg`     | Latest pre-encoded JPEG frame      |
| GET    | `/info`    | `CameraInfoResponse` | Current frame metadata          |
| GET    | `/stats`   | `CameraStatsResponse`| Aggregated runtime statistics |

## Environment Variables

| Variable       | Default | Description                  |
|----------------|---------|------------------------------|
| `CAMERA_INDEX` | 0       | OpenCV camera device index   |
| `JPEG_QUALITY` | 85      | JPEG compression quality     |
| `FRAME_WIDTH`  | 640     | Target capture width         |
| `FRAME_HEIGHT` | 480     | Target capture height        |
| `DEFAULT_FPS`  | 30      | Expected camera FPS          |
| `PORT`         | 8005    | HTTP listen port             |
| `LOG_LEVEL`    | INFO    | Logging level                |

## Design

```
[Webcam] --> [Background Thread] --> [latest_frame / latest_jpeg in RAM]
                                          |
                               Thread-safe with threading.Lock
                                          |
                          +---------------+---------------+
                          |               |               |
                    GET /frame      GET /info      GET /stats
```

- Camera is opened once in the FastAPI lifespan startup
- Background thread reads frames continuously at camera-native FPS (~30)
- Each frame is immediately JPEG-encoded and stored behind a lock
- API endpoints read from the lock-protected cache (zero encode overhead)

## Usage by Other Services

### Driver Service (20-30 FPS)
```
GET http://camera-service:8005/frame
```
Called every ~33-50ms for continuous EAR/PERCLOS analysis.

### Seatbelt Service (~1 per 3s)
```
GET http://camera-service:8005/frame
```
Called every 3 seconds for periodic YOLO seatbelt detection.

Both services receive pre-encoded JPEG frames without adding any load to the camera capture pipeline.

## Run Locally

```bash
cd services/camera-service
pip install -r requirements.txt
python main.py
```

## Docker

```bash
docker build -t camera-service .
docker run -p 8005:8005 camera-service
```
