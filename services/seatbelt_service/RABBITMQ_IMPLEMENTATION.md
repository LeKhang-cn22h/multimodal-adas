# TAI LIEU TRIEN KHAI RABBITMQ - SEATBELT-SERVICE

---

# 1 Yeu Cau Nguoi Dung

## Yeu cau nghiep vu

Seatbelt-Service la dich vu phat hien day an toan su dung YOLO. Dich vu nhan khung hinh tu Camera-Service qua RabbitMQ, chay suy luan YOLO, va phat hanh ket qua tro lai.

## Yeu cau chuc nang

| STT | Chuc nang | Mo ta |
|-----|-----------|-------|
| 1 | Nhan khung hinh | Tieu thu JPEG frames tu queue seatbelt.frames. |
| 2 | Giai ma JPEG | Chuyen doi JPEG bytes → numpy array BGR. |
| 3 | Chay YOLO inference | Su dung model best_1.pt de phat hien day an toan va cac doi tuong khac. |
| 4 | Phat hanh ket qua | Gui ket qua phan tich len seatbelt.results queue. |
| 5 | Theo doi streak | Dem so frame lien tiep khong co seatbelt → warning threshold. |
| 6 | API giam sat | /health, /check, /stats cho giam sat he thong. |

## Yeu cau phi chuc nang

- **Khong dong bo**: Xu ly frame doc lap, khong block camera.
- **Kha nang phuc hoi**: Tu dong ket noi lai RabbitMQ khi mat ket noi.
- **Khong thay doi AI**: Toan bo YOLO logic duoc giu nguyen.
- **Thread-safe**: Nhieu frame co the duoc xu ly tuan tu qua queue.

---

# 2 Tinh Nang

## 2.1 Consumer bat dong bo
- Lang nghe queue `seatbelt.frames` trong background thread rieng.
- KHONG block FastAPI request/response cycle.

## 2.2 YOLO inference khong thay doi
- Model: `best_1.pt` (7 classes).
- Confidence threshold: 0.3 (co the cau hinh).
- Class ID 6 = seatbelt.

## 2.3 Sliding window warning
- Dem so frame lien tiep KHONG co seatbelt.
- Neu streak > WARNING_FRAMES → trang thai warning = True.

## 2.4 Result publisher
- Dinh dang JSON: frame_id, timestamp, seatbelt (bool), confidence (float).
- Routing key: `seatbelt.result`.

## 2.5 Tu dong ket noi lai
- Exponential backoff giong Camera-Service.
- Tu dong tao lai channel neu bi dong.

---

# 3 Giai Phap Ky Thuat

## 3.1 Kien truc

```
┌─────────────────────────────────────────────┐
│              Seatbelt-Service                │
│                                              │
│  ┌──────────────┐                           │
│  │ FastAPI       │  /health, /check, /stats │
│  │ Main Thread   │                           │
│  └──────────────┘                           │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │       MessagingOrchestrator          │   │
│  │                                      │   │
│  │  ┌──────────────────────────────┐   │   │
│  │  │ RabbitMQConnectionManager    │   │   │
│  │  └──────────────────────────────┘   │   │
│  │                                      │   │
│  │  ┌────────────┐  ┌────────────────┐ │   │
│  │  │ Frame      │  │ Result         │ │   │
│  │  │ Consumer   │  │ Publisher      │ │   │
│  │  │ (thread)   │  │                │ │   │
│  │  └─────┬──────┘  └───────▲────────┘ │   │
│  │        │                 │          │   │
│  │  ┌─────▼─────────────────┴──────┐   │   │
│  │  │       SeatbeltDetector       │   │   │
│  │  │  (YOLO inference - GIU NGUYEN)│   │   │
│  │  └──────────────────────────────┘   │   │
│  └──────────────────────────────────────┘   │
│                                              │
└──────────────┬──────────────────┬────────────┘
               │                  │
        ┌──────▼─────┐    ┌──────▼──────┐
        │ seatbelt.  │    │ seatbelt.   │
        │ frames     │    │ results     │
        │ (in)       │    │ (out)       │
        └────────────┘    └─────────────┘
             RabbitMQ
```

## 3.2 Thay doi so voi HTTP (cu)

| Thanh phan | Truoc (HTTP) | Sau (RabbitMQ) |
|------------|-------------|-----------------|
| Nguon frame | `httpx.get(camera/frame)` | `basic_consume(seatbelt.frames)` |
| Tan suat | Moi 3 giay (polling) | Do Camera-Service quyet dinh |
| Gui ket qua | Chi qua API /check | Publish JSON len RabbitMQ |
| Do tre | HTTP round-trip + polling interval | Gan nhu real-time |
| Kha nang mo rong | 1-1 giua camera va seatbelt | Nhieu consumer tren cung queue |

---

# 4 Logic + AI

## 4.1 Luong hoat dong runtime

```
START
  │
  ▼
┌──────────────────────┐
│ Tai YOLO model       │
│ SeatbeltDetector     │
│ .load_model()        │
│ model = YOLO(best.pt)│
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Ket noi RabbitMQ      │
│ RabbitMQConnection   │
│ Manager.connect()    │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Bat dau FrameConsumer │
│ (background thread)  │
└──────────┬───────────┘
           │
     ┌─────▼─────┐
     │ CONSUME   │
     │ LOOP      │
     └─────┬─────┘
           │
    ┌──────▼──────┐
    │ Nhan frame  │
    │ tu queue    │
    │ JPEG bytes  │
    │ + headers   │
    └──────┬──────┘
           ▼
    ┌──────────────────┐
    │ Giai ma JPEG      │
    │ np.frombuffer()   │
    │ cv2.imdecode()    │
    │ → BGR numpy array │
    └──────┬───────────┘
           ▼
    ┌──────────────────────────┐
    │ Chay YOLO inference      │
    │ model(frame, conf=0.3)   │
    │                          │
    │ ┌──────────────────────┐ │
    │ │ Duyet qua cac box    │ │
    │ │ kiem tra class_id    │ │
    │ │                      │ │
    │ │ class_id == 6?       │ │
    │ │   YES → seatbelt=OK  │ │
    │ │   NO  → seatbelt=MISS│ │
    │ └──────────────────────┘ │
    └──────┬───────────────────┘
           ▼
    ┌──────────────────────┐
    │ Cap nhat streak       │
    │ if seatbelt: streak=0 │
    │ else:       streak++  │
    │                      │
    │ if streak > 10?      │
    │   warning = True     │
    └──────┬───────────────┘
           ▼
    ┌──────────────────────┐
    │ Phat hanh ket qua     │
    │ ResultPublisher       │
    │ .publish({           │
    │   frame_id,          │
    │   timestamp,          │
    │   seatbelt: bool,    │
    │   confidence: float   │
    │ })                   │
    │ → seatbelt.result    │
    └──────────────────────┘
```

## 4.2 Cac class YOLO

| Class ID | Ten | Mo ta |
|----------|-----|-------|
| 0 | cell phone | Su dung dien thoai |
| 1 | drinking | Uong nuoc |
| 2 | eyeglass | Kinh mat |
| 3 | hands off | Tay roi vo lang |
| 4 | hands on | Tay tren vo lang |
| 5 | mask | Khau trang |
| 6 | seatbelt | Day an toan |

---

# 5 Trien Khai

## 5.1 Module moi

### `messaging/consumer.py` - FrameConsumer
- Thay the hoan toan `_fetch_frame()` HTTP cua SeatbeltDetector.
- Chay trong thread rieng, lang nghe queue `seatbelt.frames`.
- Moi frame nhan duoc:
  1. Trich xuat JPEG bytes tu body.
  2. Doc frame_id, timestamp tu headers.
  3. Goi `detector.process(jpeg_bytes, frame_id, timestamp)`.
  4. Goi `publisher.publish(result)`.

### `messaging/publisher.py` - ResultPublisher
- Phat hanh ket qua duoi dang JSON.
- Routing key: `seatbelt.result`.
- Auto-reconnect khi channel dong.

### `messaging/orchestrator.py` - MessagingOrchestrator
- Khoi tao va quan ly vong doi tat ca thanh phan RabbitMQ.
- `start()`: connect → load model → start publisher → start consumer.
- `stop()`: stop consumer → stop publisher → close connection.

## 5.2 Module chinh sua

### `services/seatbelt_detector.py` - SeatbeltDetector
- **GIU NGUYEN**: `load_model()`, `_run_inference()`, `_decode_jpeg()`, `_update_stats()`.
- **THAY DOI**: 
  - Xoa `_fetch_frame()` (HTTP goi den Camera-Service).
  - Xoa `check_frame()`.
  - Them `process(jpeg_bytes, frame_id, timestamp)` → nhan JPEG bytes truc tiep.
  - Them `_build_result()` → tao ket qua dinh dang cho RabbitMQ.
  - Them `get_latest_result()` → cho API /check.
- **KHONG DOI**: Toan bo logic phat hien YOLO.

### `api/seatbelt.py` - API Routes
- **GIU NGUYEN**: `/health`, `/check`, `/stats`.
- **THAY DOI**: Su dung `get_orchestrator()` thay vi `detector` truc tiep.

### `app/main.py` - FastAPI Entry Point
- **THAY DOI**: Lifespan su dung `MessagingOrchestrator`.
- Tai YOLO model + ket noi RabbitMQ khi startup.
- Dung tat ca khi shutdown.

## 5.3 Cau hinh moi

```bash
# RabbitMQ Configuration
RABBITMQ_HOST=rabbitmq       # Ten container RabbitMQ
RABBITMQ_PORT=5672
RABBITMQ_VHOST=/
RABBITMQ_USER=guest
RABBITMQ_PASS=guest
```

## 5.4 Docker

### Dockerfile thay doi
```dockerfile
# CMD cu:
CMD ["python", "main.py"]

# CMD moi:
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
```

### docker-compose.yml thay doi
- Them `seatbelt-service` (truoc day chay ngoai Docker).
- Them `RABBITMQ_*` environment variables.
- Depends on `rabbitmq` voi healthcheck.

---

# 6 Kiem Thu

## 6.1 Unit Test

| Test | Mo ta |
|------|-------|
| `test_decode_jpeg` | Kiem tra giai ma JPEG bytes → numpy array. |
| `test_decode_jpeg_invalid` | Dau vao khong hop le → return None. |
| `test_build_result_seatbelt_true` | Kiem tra ket qua co seatbelt=True. |
| `test_build_result_seatbelt_false` | Kiem tra ket qua co seatbelt=False. |
| `test_update_stats_seatbelt_ok` | Kiem tra streak reset ve 0 khi phat hien seatbelt. |
| `test_update_stats_seatbelt_missing` | Kiem tra streak tang khi khong co seatbelt. |
| `test_warning_threshold` | Kiem tra warning=True khi streak > WARNING_FRAMES. |

## 6.2 Integration Test

| Test | Mo ta |
|------|-------|
| `test_consume_frame_and_publish` | Gui frame qua RabbitMQ → kiem tra ket qua duoc publish. |
| `test_rabbitmq_reconnect` | Dung RabbitMQ → khoi dong lai → kiem tra consumer tu dong ket noi lai. |
| `test_multiple_frames_ordering` | Gui 100 frame → kiem tra thu tu xu ly FIFO. |
| `test_concurrent_consumers` | Chay 2 instance seatbelt-service → kiem tra phan phoi frame round-robin. |
| `test_empty_frame` | Gui frame khong co nguoi → kiem tra ket qua seatbelt=False. |
| `test_docker_compose` | `docker-compose up seatbelt-service` → kiem tra hoat dong. |

## 6.3 Stress Test

| Test | Mo ta |
|------|-------|
| `test_high_frame_rate` | Gui 10 frame/giay → kiem tra YOLO xu ly kip. |
| `test_large_queue_backlog` | Gui 1000 frame truoc khi consumer chay → kiem tra xu ly het. |
| `test_graceful_shutdown` | SIGTERM trong luc dang xu ly → kiem tra khong crash. |

## 6.4 Cach chay

```bash
cd services/seatbelt_service

# Unit test
pip install pytest pytest-cov
pytest tests/ -v --cov=app

# Integration test (can RabbitMQ)
docker run -d --name test-rabbitmq -p 5672:5672 rabbitmq:3.12-management-alpine
RABBITMQ_HOST=localhost pytest tests/ -v -m integration
```
