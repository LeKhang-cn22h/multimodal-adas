# TAI LIEU TRIEN KHAI RABBITMQ - CAMERA-SERVICE

---

# 1 Yeu Cau Nguoi Dung

## Yeu cau nghiep vu

Camera-Service la dich vu dau vao cua he thong ADAS, chiu trach nhiem:
- Thu nhận hình ảnh liên tục từ webcam.
- Phan phoi khung hinh den cac dich vu AI (Driver-Service, Seatbelt-Service).
- Nhan ket qua suy luan AI va hien thi len man hinh giam sat.
- KHONG thuc hien bat ky suy luan AI nao.

## Yeu cau chuc nang

| STT | Chuc nang | Mo ta |
|-----|-----------|-------|
| 1 | Khoi dong camera | Mo webcam va bat dau thu nhận khung hinh. |
| 2 | Dung camera | Dong webcam va giai phong tai nguyen. |
| 3 | Thu nhận khung hinh lien tuc | Vong lap doc frame tu webcam o toc do toi da phan cung ho tro. |
| 4 | Ma hoa JPEG | Chuyen doi moi khung hinh BGR sang dinh dang JPEG bytes. |
| 5 | Phat hanh khung hinh Driver | Gui MOI khung hinh den queue driver.frames qua RabbitMQ. |
| 6 | Phat hanh khung hinh Seatbelt | Gui 1 khung hinh den queue seatbelt.frames theo khoang thoi gian cau hinh (mac dinh 10 phut). |
| 7 | Tieu thu ket qua Driver | Lang nghe queue driver.results de nhan ket qua phat hien buon ngu. |
| 8 | Tieu thu ket qua Seatbelt | Lang nghe queue seatbelt.results de nhan ket qua phat hien day an toan. |
| 9 | Hien thi OpenCV | Su dung cv2.imshow de hien thi luong camera truc tiep. |
| 10 | Ve overlay ket qua AI | Hien thi ket qua moi nhat (Sleepy, Seatbelt, FPS) tren khung hinh. |
| 11 | API Health Check | Endpoint /health, /frame, /info, /stats cho giam sat he thong. |

## Yeu cau phi chuc nang

- **Doc lap**: Camera FPS KHONG phu thuoc vao toc do suy luan AI.
- **Khong dong bo**: Camera KHONG bao gio cho Driver hoac Seatbelt xu ly xong.
- **Kha nang phuc hoi**: Tu dong ket noi lai khi mat ket noi RabbitMQ hoac webcam.
- **Kha nang mo rong**: Dang ky nhieu consumer cho cung mot queue.
- **Dung luong thap**: Su dung JPEG nen de giam bang thong RabbitMQ.

---

# 2 Tinh Nang

## 2.1 Phat hanh khung hinh bat dong bo
- Moi khung hinh duoc ma hoa thanh JPEG va phat hanh ngay lap tuc qua RabbitMQ.
- KHONG cho phan hoi tu Driver hoac Seatbelt.
- FPS camera duoc duy tri doc lap.

## 2.2 Phat hanh khung hinh Seatbelt co dieu chinh
- Mac dinh 10 phut/khung hinh (co the cau hinh qua SEATBELT_FRAME_INTERVAL).
- Giam tai RabbitMQ cho dich vu khong can thoi gian thuc.

## 2.3 Tieu thu ket qua AI
- Lang nghe 2 queue ket qua: driver.results va seatbelt.results.
- Luu tru ket qua moi nhat trong bo nho (thread-safe).

## 2.4 Hien thi OpenCV voi overlay
- Thread rieng biet cho hien thi, khong anh huong den capture.
- Overlay FPS, trang thai Sleepy, trang thai Seatbelt.

## 2.5 Tu dong ket noi lai
- RabbitMQ: Exponential backoff (1s -> 2s -> 4s -> ... -> 30s).
- Webcam: Tu dong phat hien mat ket noi va thu ket noi lai.

---

# 3 Giai Phap Ky Thuat

## 3.1 Vi sao chon RabbitMQ

| Tieu chi | HTTP dong bo (cu) | RabbitMQ (moi) |
|----------|-------------------|-----------------|
| Phu thuoc toc do AI | Camera FPS bi giam neu AI cham | Camera FPS doc lap hoan toan |
| Mo hinh giao tiep | 1-1 dong bo | N-N bat dong bo |
| Kha nang mo rong | Kho (can load balancer) | De (chi can them consumer) |
| Kha nang phuc hoi | That bai ngay neu dich vu dich chet | Hang doi luu tru, xu ly sau |
| Bang thong | Dung luong cao (HTTP headers) | Toi uu (binary body + headers) |

## 3.2 Kien truc

```
┌─────────────────────────────────────────────┐
│              Camera-Service                  │
│                                              │
│  ┌──────────┐    ┌──────────────┐           │
│  │ Webcam   │───▶│ CameraManager │           │
│  │ Capture  │    │ (Background) │           │
│  └──────────┘    └──────┬───────┘           │
│                         │                   │
│              ┌──────────▼──────────┐        │
│              │   on_frame callback │        │
│              └──────────┬──────────┘        │
│                         │                   │
│         ┌───────────────┼──────────────┐    │
│         ▼                               ▼    │
│  ┌──────────────┐              ┌──────────────┐
│  │Driver        │              │Seatbelt      │
│  │Publisher     │              │Publisher     │
│  │(every frame) │              │(throttled)   │
│  └──────┬───────┘              └──────┬───────┘
│         │                             │
├─────────┼─────────────────────────────┼────────┤
│         ▼         RabbitMQ            ▼        │
│  ┌──────────┐              ┌──────────────┐   │
│  │driver.   │              │seatbelt.     │   │
│  │frames    │              │frames        │   │
│  └──────────┘              └──────────────┘   │
│                                               │
│  ┌──────────┐              ┌──────────────┐   │
│  │driver.   │              │seatbelt.     │   │
│  │results   │              │results       │   │
│  └────┬─────┘              └──────┬───────┘   │
│       │                           │           │
│  ┌────▼──────┐              ┌─────▼───────┐   │
│  │Result     │              │Display      │   │
│  │Consumer   │──────────────▶ Overlay     │   │
│  └───────────┘              └──────┬──────┘   │
│                                    │          │
│                              ┌─────▼──────┐   │
│                              │ cv2.imshow │   │
│                              └────────────┘   │
└─────────────────────────────────────────────┘
```

## 3.3 Producer
- `FramePublisher`: Chiu trach nhiem phat hanh JPEG bytes len exchange.
- Dinh tuyen: `driver.frame` cho Driver-Service, `seatbelt.frame` cho Seatbelt-Service.
- Body message: Raw JPEG bytes (toi uu bang thong).
- Headers: frame_id, timestamp (khong nam trong body).

## 3.4 Consumer
- `ResultConsumer`: Chay trong background thread rieng.
- Dang ky 2 queue: `driver.results` + `seatbelt.results`.
- Parse JSON ket qua thanh Pydantic model.
- Luu tru ket qua moi nhat (thread-safe lock).

## 3.5 Exchange
- Ten: `adas.exchange`
- Loai: `topic`
- Durable: True (ton tai sau khi restart RabbitMQ)

## 3.6 Queues

| Queue | Routing Key | Durable | Mo ta |
|-------|------------|---------|-------|
| driver.frames | driver.frame | True | Khung hinh cho Driver-Service |
| seatbelt.frames | seatbelt.frame | True | Khung hinh cho Seatbelt-Service |
| driver.results | driver.result | True | Ket qua phat hien buon ngu |
| seatbelt.results | seatbelt.result | True | Ket qua phat hien day an toan |

## 3.7 Chien luoc ket noi lai

- **Exponential Backoff**: 1s → 2s → 4s → 8s → 16s → 30s (cap).
- **Phat hien loi**: Bat AMQPConnectionError, AMQPChannelError, ConnectionClosedByBroker.
- **Phuc hoi kenh**: Tao kenh moi tu connection hien co.
- **Phuc hoi connection**: Tao connection moi neu connection hien co da dong.

## 3.8 Threading / Async

Camera-Service su dung 4 thread chinh:
1. **Camera Capture Thread**: Vong lap doc webcam + encode JPEG.
2. **Result Consumer Thread**: Lang nghe RabbitMQ ket qua AI.
3. **Display Thread**: Hien thi OpenCV cv2.imshow + overlay.
4. **FastAPI Main Thread**: Xu ly HTTP requests (/health, /stats, ...).

Tat ca thread doc lap, KHONG block lan nhau.

## 3.9 Luong tin nhan

```
Webcam → CameraManager._capture_loop()
  │
  ├──▶ on_frame_callback(jpeg_bytes, frame_id, timestamp)
  │      │
  │      ├──▶ FramePublisher("driver.frame").publish(jpeg) → driver.frames
  │      │
  │      └──▶ [neu dat nguong thoi gian]
  │           FramePublisher("seatbelt.frame").publish(jpeg) → seatbelt.frames
  │
  ▼
ResultConsumer nhận:
  driver.results  → parse JSON → DriverResultMessage → Display.update_driver_result()
  seatbelt.results → parse JSON → SeatbeltResultMessage → Display.update_seatbelt_result()

Display._display_loop():
  frame = camera_manager.latest_frame
  frame = draw_hud(frame, sleepy, seatbelt, fps)
  cv2.imshow("ADAS Monitor", frame)
```

## 3.10 Tai sao thiet ke nay co kha nang mo rong

- **Queue doc lap**: Moi loai AI co queue rieng → de dang them AI moi.
- **Topic exchange**: Co the them routing key moi ma khong thay doi code cu.
- **Nhieu consumer**: Cung mot queue co the co nhieu consumer (round-robin).
- **Khong dong bo**: Tat ca giao tiep qua message → de dang phan tan microservice.
- **Luu tru ben vung**: Neu mot service sap, message van nam trong queue cho den khi service online tro lai.

---

# 4 Logic + AI

## 4.1 Camera-Service

### Luong hoat dong runtime

```
┌─────────┐
│ START   │
└────┬────┘
     ▼
┌────────────────┐
│ Mo Webcam      │
│ CameraManager  │
│ .start()       │
└────┬───────────┘
     ▼
┌────────────────────────────────────────────┐
│              CAPTURE LOOP                  │
│  (background thread - khong dong bo)       │
│                                            │
│  ┌──────────────────────────┐             │
│  │ Doc frame tu webcam      │             │
│  │ cv2.VideoCapture.read() │             │
│  └────────┬─────────────────┘             │
│           ▼                                │
│  ┌──────────────────────────┐             │
│  │ Ma hoa JPEG               │             │
│  │ cv2.imencode(".jpg")     │             │
│  └────────┬─────────────────┘             │
│           ▼                                │
│  ┌──────────────────────────┐             │
│  │ Luu latest_frame +       │             │
│  │ latest_jpeg (thread-lock)│             │
│  └────────┬─────────────────┘             │
│           ▼                                │
│  ┌──────────────────────────┐             │
│  │ Goi on_frame_callback()  │             │
│  │ (non-blocking)           │             │
│  └────────┬─────────────────┘             │
│           │                                │
└───────────┼────────────────────────────────┘
            │
    ┌───────┴──────┐
    ▼              ▼
┌─────────┐  ┌──────────────┐
│Driver   │  │Seatbelt      │
│Publisher│  │Publisher     │
│         │  │(throttled)   │
│Publish  │  │Publish       │
│MỖI frame│  │MỖI 10 phút  │
└────┬────┘  └──────┬───────┘
     │              │
     ▼              ▼
┌──────────────────────────┐
│        RabbitMQ           │
│  driver.frames            │
│  seatbelt.frames          │
└──────────────────────────┘

     ▲              ▲
     │              │
┌────┴────┐  ┌─────┴──────┐
│driver.  │  │seatbelt.   │
│results  │  │results     │
│Consumer │  │Consumer    │
└────┬────┘  └─────┬──────┘
     │              │
     ▼              ▼
┌──────────────────────────┐
│    Display Thread        │
│                          │
│ ┌──────────────────────┐ │
│ │ latest_frame (camera)│ │
│ │ + result (sleepy)    │ │
│ │ + result (seatbelt)  │ │
│ │ = overlay            │ │
│ └──────────┬───────────┘ │
│            ▼             │
│ ┌──────────────────────┐ │
│ │ cv2.imshow()         │ │
│ │ "ADAS Monitor"       │ │
│ └──────────────────────┘ │
└──────────────────────────┘
```

## 4.2 Driver-Service

```
┌──────────────┐
│ FrameConsumer│
│ thread       │
└──────┬───────┘
       ▼
┌──────────────────────┐
│ Consume frame tu     │
│ driver.frames queue  │
│ (JPEG bytes + headers)│
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ Decode JPEG          │
│ cv2.imdecode() → BGR │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ FatigueDetector      │
│ .process()           │
│                      │
│ ┌──────────────────┐ │
│ │ BGR → RGB        │ │
│ └──────┬───────────┘ │
│        ▼             │
│ ┌──────────────────┐ │
│ │ MediaPipe         │ │
│ │ FaceLandmarker    │ │
│ │ detect_for_video()│ │
│ └──────┬───────────┘ │
│        ▼             │
│ ┌──────────────────┐ │
│ │ Left EAR +        │ │
│ │ Right EAR         │ │
│ │ (calculate_ear()) │ │
│ └──────┬───────────┘ │
│        ▼             │
│ ┌──────────────────┐ │
│ │ Sliding Window    │ │
│ │ Logic             │ │
│ │                    │ │
│ │ EAR < threshold?  │ │
│ │   YES → counter++ │ │
│ │   NO  → counter=0 │ │
│ │                    │ │
│ │ counter > 60?     │ │
│ │   YES → SLEEPY    │ │
│ │   NO  → AWAKE     │ │
│ └──────┬───────────┘ │
└────────┼─────────────┘
         ▼
┌──────────────────────┐
│ ResultPublisher      │
│ .publish(result)     │
│ → driver.results     │
│ routing_key:         │
│   driver.result      │
└──────────────────────┘
```

## 4.3 Seatbelt-Service

```
┌──────────────┐
│ FrameConsumer│
│ thread       │
└──────┬───────┘
       ▼
┌──────────────────────┐
│ Consume frame tu     │
│ seatbelt.frames queue│
│ (JPEG bytes + headers)│
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ Decode JPEG          │
│ cv2.imdecode() → BGR │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ SeatbeltDetector     │
│ .process()           │
│                      │
│ ┌──────────────────┐ │
│ │ YOLO Model        │ │
│ │ (best_1.pt)       │ │
│ │ model(frame)      │ │
│ └──────┬───────────┘ │
│        ▼             │
│ ┌──────────────────┐ │
│ │ Phan tich boxes   │ │
│ │                    │ │
│ │ Co class_id=6?    │ │
│ │ (seatbelt class)  │ │
│ │   YES → OK        │ │
│ │   NO  → MISSING   │ │
│ │                    │ │
│ │ Tracking streak   │ │
│ │ > 10? → WARNING   │ │
│ └──────┬───────────┘ │
└────────┼─────────────┘
         ▼
┌──────────────────────┐
│ ResultPublisher      │
│ .publish(result)     │
│ → seatbelt.results   │
│ routing_key:         │
│   seatbelt.result    │
└──────────────────────┘
```

---

# 5 Trien Khai

## 5.1 Cau truc thu muc Camera-Service

```
services/camera-service/
├── Dockerfile
├── main.py                    # Entry point: chay uvicorn
├── requirements.txt           # pika + fastapi + opencv + numpy + pydantic
├── desktop_monitor.py         # [KHONG SU DUNG - da duoc thay the bang display.py]
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app voi lifespan (RabbitMQ + CameraManager)
│   ├── api/
│   │   └── camera.py          # Routes: /health, /frame, /info, /stats
│   ├── core/
│   │   └── config.py          # Settings: camera + RabbitMQ config
│   ├── messaging/
│   │   ├── __init__.py
│   │   ├── connection.py      # RabbitMQConnectionManager: ket noi + reconnect
│   │   ├── publisher.py       # FramePublisher: phat hanh JPEG frames
│   │   ├── consumer.py        # ResultConsumer: nhan ket qua AI
│   │   └── orchestrator.py    # MessagingOrchestrator: dieu phoi vong doi
│   ├── models/
│   │   ├── __init__.py
│   │   └── messages.py        # FrameMessage, DriverResultMessage, SeatbeltResultMessage
│   ├── services/
│   │   ├── __init__.py
│   │   ├── camera_manager.py  # CameraManager: capture webcam + encode JPEG
│   │   ├── camera_manager_instance.py  # Singleton
│   │   └── display.py         # DisplayOverlay: cv2.imshow + HUD
│   ├── schemas/
│   │   └── camera.py          # Pydantic schemas cho API
│   └── utils/
│       ├── __init__.py
│       └── logger.py          # Logger thread-safe
```

## 5.2 Cau truc thu muc Driver-Service

```
services/driver-service/
├── Dockerfile
├── main.py                    # [GIU NGUYEN - tham khao AI goc]
├── requirements.txt           # mediapipe + pika + scipy + fastapi
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app voi lifespan (RabbitMQ + AI)
│   ├── api/
│   │   └── fatigue.py         # Routes: /health, /stats
│   ├── core/
│   │   └── config.py          # Settings: EAR threshold + RabbitMQ config
│   ├── messaging/
│   │   ├── __init__.py
│   │   ├── connection.py      # RabbitMQConnectionManager
│   │   ├── publisher.py       # ResultPublisher: phat hanh ket qua buon ngu
│   │   ├── consumer.py        # FrameConsumer: tieu thu khung hinh
│   │   └── orchestrator.py    # MessagingOrchestrator
│   ├── services/
│   │   └── fatigue_detector.py # FatigueDetector: MediaPipe + EAR + sliding window
│   └── utils/
│       ├── __init__.py
│       ├── ear.py             # calculate_ear() - AI GOC
│       └── logger.py          # Logger
```

## 5.3 Cau truc thu muc Seatbelt-Service

```
services/seatbelt_service/
├── Dockerfile
├── main.py                    # Entry point: chay uvicorn
├── requirements.txt           # ultralytics + pika + fastapi
├── best_1.pt                  # YOLO model
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app voi lifespan (RabbitMQ + YOLO)
│   ├── api/
│   │   └── seatbelt.py        # Routes: /health, /check, /stats
│   ├── core/
│   │   └── config.py          # Settings: YOLO + RabbitMQ config
│   ├── messaging/
│   │   ├── __init__.py
│   │   ├── connection.py      # RabbitMQConnectionManager
│   │   ├── publisher.py       # ResultPublisher: phat hanh ket qua seatbelt
│   │   ├── consumer.py        # FrameConsumer: tieu thu khung hinh
│   │   └── orchestrator.py    # MessagingOrchestrator
│   ├── services/
│   │   ├── seatbelt_detector.py # SeatbeltDetector: YOLO inference (GIU NGUYEN AI)
│   │   └── detector_instance.py
│   ├── schemas/
│   │   └── seatbelt.py        # Pydantic schemas cho API
│   └── utils/
│       ├── __init__.py
│       └── logger.py          # Logger
```

## 5.4 Giai thich cac module

### Camera-Service

#### `messaging/connection.py` - RabbitMQConnectionManager
- **Khoi tao**: Nhan host, port, vhost, username, password, heartbeat.
- **`connect()`**: Thiet lap ket noi den RabbitMQ voi retry exponential backoff.
- **`create_channel()`**: Tao kenh moi tu connection hien co.
- **`close()`**: Gui tin hieu dung (stop_event) va dong ket noi.
- **`is_connected`**: Kiem tra trang thai ket noi.

#### `messaging/publisher.py` - FramePublisher
- **`__init__(connection_manager, routing_key)`**: Khoi tao voi ket noi va routing key cu the.
- **`start()`**: Tao kenh, khai bao exchange "adas.exchange" (topic, durable).
- **`publish(jpeg_bytes, metadata)`**: Phat hanh 1 frame len exchange.
  - Body: Raw JPEG bytes.
  - Properties.headers: frame_id, timestamp.
  - Delivery mode: persistent (2).
  - Content type: image/jpeg.
  - Tu dong retry neu channel dong.
- **`stop()`**: Dong kenh publisher.

#### `messaging/consumer.py` - ResultConsumer
- **`__init__(connection_manager)`**: Khoi tao voi ket noi.
- **`on_driver_result(callback)`**: Dang ky callback cho ket qua Driver.
- **`on_seatbelt_result(callback)`**: Dang ky callback cho ket qua Seatbelt.
- **`start()`**: Tao thread moi chay `_consume_loop()`.
- **`_consume_loop()`**: 
  - Khai bao exchange.
  - Tao queue "driver.results" + bind "driver.result".
  - Tao queue "seatbelt.results" + bind "seatbelt.result".
  - `basic_consume()` voi auto_ack.
  - `start_consuming()` (blocking).
  - Tu dong reconnect khi mat ket noi.
- **`latest_driver_result`**: Property thread-safe tra ve ket qua driver moi nhat.
- **`latest_seatbelt_result`**: Property thread-safe tra ve ket qua seatbelt moi nhat.
- **`stop()`**: Cancel consumer + dong kenh.

#### `messaging/orchestrator.py` - MessagingOrchestrator
- Dieu phoi toan bo vong doi RabbitMQ trong Camera-Service.
- **`start()`**: Ket noi RabbitMQ → tao publishers → wire camera callback → tao consumer → tao display.
- **`stop()`**: Tat display → dung consumer → dung publishers → dong connection.
- **`_on_frame_captured(jpeg_bytes, frame_id, timestamp)`**: Goi boi CameraManager moi frame.
  - Phat hanh den driver.frames (moi frame).
  - Phat hanh den seatbelt.frames (throttled theo SEATBELT_FRAME_INTERVAL).

#### `services/camera_manager.py` - CameraManager (da chinh sua)
- **Thay doi duy nhat**: Them `set_on_frame_callback()`.
- **`_capture_loop()`**: Sau khi encode JPEG thanh cong, goi callback (neu co).
- **GIU NGUYEN**: Toan bo logic capture, encode, reconnect webcam.

#### `services/display.py` - DisplayOverlay
- **`__init__(camera_manager)`**: Nhan tham chieu den CameraManager.
- **`update_driver_result(result)`**: Cap nhat ket qua driver moi nhat (thread-safe).
- **`update_seatbelt_result(result)`**: Cap nhat ket qua seatbelt moi nhat (thread-safe).
- **`start()`**: Tao thread hien thi rieng.
- **`_display_loop()`**:
  - Tao cua so OpenCV "ADAS Monitor".
  - Vong lap: lay latest_frame → ve HUD → cv2.imshow → cv2.waitKey(1).
  - Thoat khi nhan phim 'q' hoac ESC.
  - Duy tri FPS hien thi ~30.
- **`_draw_hud(frame)`**: Ve overlay Sleepy/Sentbelt/FPS len khung hinh.

#### `models/messages.py`
- **`FrameMessage`**: frame_id, timestamp (dung cho AMQP headers).
- **`DriverResultMessage`**: frame_id, timestamp, sleepy, confidence.
- **`SeatbeltResultMessage`**: frame_id, timestamp, seatbelt, confidence.

### Driver-Service

#### `services/fatigue_detector.py` - FatigueDetector
- **GIU NGUYEN AI**: MediaPipe FaceLandmarker, EAR tinh toan, sliding window.
- **`load_model()`**: Tai MediaPipe model "face_landmarker.task".
- **`process(jpeg_bytes, frame_id, timestamp)`**: Xu ly 1 frame.
  - Decode JPEG → BGR → RGB.
  - Chay MediaPipe FaceLandmarker.
  - Tinh left_ear + right_ear (dung calculate_ear() tu ear.py).
  - Sliding window: counter++ neu EAR < threshold; counter=0 neu >= threshold.
  - Sleepy = True neu counter > DROWSY_FRAMES.
  - Tra ve dict: frame_id, timestamp, sleepy, confidence.
- **`get_stats()`**: Thong ke: so frame da xu ly, so su kien buon ngu, EAR trung binh, inference time.

#### `utils/ear.py` - calculate_ear()
- **KHONG THAY DOI**: Nguyen ban tu driver-service/main.py.
- Ham tinh Eye Aspect Ratio tu 6 diem landmark cua mat.
- Dung scipy.spatial.distance.euclidean.

### Seatbelt-Service

#### `services/seatbelt_detector.py` - SeatbeltDetector (da chinh sua)
- **GIU NGUYEN AI**: YOLO model, class names, confidence threshold.
- **THAY DOI**: `check_frame()` → `process(jpeg_bytes, frame_id, timestamp)`.
  - Nhan JPEG bytes truc tiep (thay vi HTTP fetch).
  - Decode JPEG → numpy array.
  - Chay YOLO inference (GIONG HET ban goc).
  - Tra ve dict: frame_id, timestamp, seatbelt, confidence.
- **KHONG THAY DOI**: `_run_inference()`, `_update_stats()`, `load_model()`.

## 5.5 Vong doi RabbitMQ

```
Startup:
  1. FastAPI lifespan bắt đầu
  2. CameraManager.start() → mở webcam
  3. MessagingOrchestrator.start()
     a. RabbitMQConnectionManager.connect() → kết nối với retry
     b. driver_publisher.start() → tạo channel + khai báo exchange
     c. seatbelt_publisher.start() → tạo channel + khai báo exchange
     d. CameraManager.set_on_frame_callback(handler)
     e. consumer.start() → thread riêng, bắt đầu consume
     f. display.start() → thread hiển thị OpenCV

Shutdown:
  1. FastAPI lifespan kết thúc
  2. orchestrator.stop()
     a. CameraManager.set_on_frame_callback(None) → ngừng publish
     b. display.stop() → đóng cv2 window
     c. consumer.stop() → cancel consumer + đóng channel
     d. driver_publisher.stop() → đóng channel
     e. seatbelt_publisher.stop() → đóng channel
     f. connection_manager.close() → đóng connection
  3. camera_manager.stop() → release webcam
```

## 5.6 Vong doi Publisher

```
Publisher.start():
  channel = connection.create_channel()
  channel.exchange_declare("adas.exchange", "topic", durable=True)

Publisher.publish(jpeg_bytes, metadata):
  properties = BasicProperties(
    delivery_mode=2,
    content_type="image/jpeg",
    headers={"frame_id": ..., "timestamp": ...}
  )
  channel.basic_publish(exchange, routing_key, body=jpeg_bytes, properties=properties)

  → Nếu channel đã đóng: tự động tạo channel mới và thử lại 1 lần
  → Nếu thất bại: log warning, return False (KHÔNG throw exception)
```

## 5.7 Vong doi Consumer

```
Consumer.start():
  tạo background thread
  thread chạy _consume_loop():
    while not stop_event:
      connect() nếu chưa kết nối
      tạo channel
      khai báo exchange
      khai báo queue + bind
      basic_consume(queue, callback, auto_ack=True)
      channel.start_consuming()  → BLOCKING
      
      → nếu có exception: reconnect sau 2s

Consumer callback:
  đọc headers (frame_id, timestamp)
  parse body (JSON)
  validate với Pydantic
  cập nhật latest_result (thread-safe)
  gọi callback nếu có
```

## 5.8 Thay doi Docker

### docker-compose.yml

**Them moi**:
- Container `rabbitmq` (image: rabbitmq:3.12-management-alpine)
  - Port 5672 (AMQP), 15672 (Management UI).
  - Healthcheck: `rabbitmq-diagnostics check_port_connectivity`.
  - Network: adas-net.

**Chinh sua**:
- `camera-service` (truoc day bi comment): Bo comment, them bien moi truong RabbitMQ.
- `driver-service`: Them bien moi truong RabbitMQ, xoa `CAMERA_ID`, `AGGREGATOR_URL`.
- `seatbelt-service`: Them moi (truoc day khong co trong compose), them RABBITMQ config.

**Depends_on**:
- camera-service → rabbitmq (condition: service_healthy)
- driver-service → rabbitmq (condition: service_healthy)
- seatbelt-service → rabbitmq (condition: service_healthy)

### Dockerfile

**Camera-Service**: Them SEATBELT_FRAME_INTERVAL, giu nguyen.
**Driver-Service**: Cap nhat CMD de chay dung FastAPI app (`python -m uvicorn app.main:app`).
**Seatbelt-Service**: Cap nhat CMD de chay dung FastAPI app.

---

# 6 Kiem Thu

## 6.1 Unit Test

### Camera-Service

| Test | Mo ta | File |
|------|-------|------|
| `test_camera_manager_start_stop` | Kiem tra start/stop CameraManager. | `tests/test_camera_manager.py` |
| `test_camera_manager_frame_capture` | Kiem tra frame duoc capture va encode JPEG. | `tests/test_camera_manager.py` |
| `test_frame_message_model` | Kiem tra FrameMessage Pydantic validation. | `tests/test_models.py` |
| `test_driver_result_message_model` | Kiem tra DriverResultMessage. | `tests/test_models.py` |
| `test_seatbelt_result_message_model` | Kiem tra SeatbeltResultMessage. | `tests/test_models.py` |
| `test_display_overlay` | Kiem tra HUD drawing functions. | `tests/test_display.py` |

### Driver-Service

| Test | Mo ta | File |
|------|-------|------|
| `test_calculate_ear` | Kiem tra ham EAR voi landmark gia lap. | `tests/test_ear.py` |
| `test_fatigue_detector_decode` | Kiem tra decode JPEG bytes. | `tests/test_fatigue.py` |
| `test_fatigue_detector_result_format` | Kiem tra dinh dang ket qua. | `tests/test_fatigue.py` |

### Seatbelt-Service

| Test | Mo ta | File |
|------|-------|------|
| `test_detector_decode_jpeg` | Kiem tra ham decode JPEG. | `tests/test_detector.py` |
| `test_detector_build_result` | Kiem tra dinh dang ket qua. | `tests/test_detector.py` |
| `test_detector_update_stats` | Kiem tra thong ke duoc cap nhat dung. | `tests/test_detector.py` |

## 6.2 Integration Test

### RabbitMQ connectivity

| Test | Mo ta |
|------|-------|
| `test_connect_to_rabbitmq` | Kiem tra ket noi thanh cong den RabbitMQ. |
| `test_connection_reconnect` | Mo phong mat ket noi va kiem tra tu dong ket noi lai. |
| `test_channel_recreation` | Kiem tra kenh duoc tao lai sau khi dong. |

### Frame Publish Test

| Test | Mo ta |
|------|-------|
| `test_publish_frame` | Phat hanh 1 frame JPEG va kiem tra no xuat hien trong queue. |
| `test_publish_many_frames` | Phat hanh 1000 frame va kiem tra tat ca deu duoc nhan. |
| `test_frame_headers` | Kiem tra frame_id va timestamp trong headers. |
| `test_seatbelt_throttle` | Kiem tra seatbelt frame chi duoc publish theo interval. |

### Driver Consume Test

| Test | Mo ta |
|------|-------|
| `test_consume_and_process_frame` | Gui 1 frame, kiem tra Driver nhan va xu ly. |
| `test_sleepy_detection` | Gui nhieu frame EAR thap → kiem tra ket qua sleepy=True. |
| `test_awake_detection` | Gui frame EAR binh thuong → kiem tra ket qua sleepy=False. |

### Seatbelt Consume Test

| Test | Mo ta |
|------|-------|
| `test_consume_and_process_frame` | Gui 1 frame, kiem tra Seatbelt nhan va xu ly. |
| `test_result_published` | Kiem tra ket qua duoc publish len seatbelt.results. |

### Camera Result Consume Test

| Test | Mo ta |
|------|-------|
| `test_consume_driver_result` | Publish ket qua driver vao queue → kiem tra camera nhan duoc. |
| `test_consume_seatbelt_result` | Publish ket qua seatbelt vao queue → kiem tra camera nhan duoc. |
| `test_result_thread_safety` | Gui nhieu ket qua dong thoi → kiem tra khong co race condition. |

### Overlay Test

| Test | Mo ta |
|------|-------|
| `test_hud_sleepy_yes` | Kiem tra HUD hien thi "Sleepy : YES". |
| `test_hud_sleepy_no` | Kiem tra HUD hien thi "Sleepy : NO". |
| `test_hud_seatbelt_yes` | Kiem tra HUD hien thi "Seatbelt : YES". |
| `test_hud_seatbelt_no` | Kiem tra HUD hien thi "Seatbelt : NO". |
| `test_hud_fps_format` | Kiem tra FPS hien thi dung dinh dang. |

## 6.3 Stress Test

| Test | Mo ta |
|------|-------|
| `test_high_fps_publish` | Phat hanh 60+ FPS trong 30 giay → kiem tra khong mat frame. |
| `test_queue_overflow` | Phat hanh 10000 frame trong khi consumer offline → kiem tra queue khong bi loi. |
| `test_consumer_lag` | Consumer cham hon publisher 10x → kiem tra he thong van hoat dong. |
| `test_graceful_shutdown` | Dung service giua luc dang xu ly → kiem tra khong crash. |
| `test_docker_compose` | `docker-compose up` → kiem tra tat ca service hoat dong. |

## 6.4 Cach chay test

```bash
# Unit test (khong can RabbitMQ)
cd services/camera-service
pip install pytest pytest-cov
pytest tests/ -v --cov=app

# Integration test (can RabbitMQ chay)
docker run -d --name test-rabbitmq -p 5672:5672 rabbitmq:3.12-management-alpine
pytest tests/ -v -m integration

# Full test voi Docker Compose
docker-compose up -d
pytest tests/ -v -m e2e
```
