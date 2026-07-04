# Logic + AI - Camera-Service

## Lưu ý quan trọng

**Camera-Service KHÔNG thực hiện bất kỳ suy luận AI nào.** Tất cả AI logic nằm ở Driver-Service (MediaPipe EAR) và Seatbelt-Service (YOLO). Camera-Service chỉ thu nhận, mã hóa, phân phối khung hình và hiển thị kết quả.

Tài liệu này mô tả luồng xử lý hệ thống (system logic), không mô tả toán học AI.

---

## Runtime Flow - Toàn bộ vòng đời

```mermaid
flowchart TD
    A[FastAPI lifespan START] --> B[CameraManager.start]
    B --> C[Mở webcam - cv2.VideoCapture]
    C --> D{Tạo Camera Capture Thread}
    D --> E[MessagingOrchestrator.start]
    E --> F[RabbitMQConnectionManager.connect]
    F --> G[DriverPublisher.start]
    G --> H[SeatbeltPublisher.start]
    H --> I[CameraManager.set_on_frame_callback]
    I --> J[ResultConsumer.start - thread riêng]
    J --> K[DisplayOverlay.start - thread riêng]
    K --> L[Hệ thống sẵn sàng - chạy liên tục]
    L --> M[FastAPI lifespan SHUTDOWN]
    M --> N[Orchestrator.stop]
    N --> O[Dừng display thread]
    O --> P[Dừng consumer thread]
    P --> Q[Dừng publishers]
    Q --> R[Đóng RabbitMQ connection]
    R --> S[CameraManager.stop]
    S --> T[Giải phóng webcam]
    T --> U[Hệ thống dừng]
```

---

## Sequence Diagram - Khởi động hệ thống

```mermaid
sequenceDiagram
    participant F as FastAPI
    participant CM as CameraManager
    participant O as MessagingOrchestrator
    participant RMQ as RabbitMQ
    participant DP as DriverPublisher
    participant SP as SeatbeltPublisher
    participant RC as ResultConsumer
    participant D as DisplayOverlay

    F->>CM: start()
    CM->>CM: _try_open_camera()
    CM->>CM: Thread(target=_capture_loop).start()
    
    F->>O: start()
    O->>RMQ: connect() [retry nếu fail]
    RMQ-->>O: connected
    
    O->>DP: start()
    DP->>RMQ: create_channel()
    DP->>RMQ: exchange_declare("adas.exchange", "topic")
    
    O->>SP: start()
    SP->>RMQ: create_channel()
    SP->>RMQ: exchange_declare("adas.exchange", "topic")
    
    O->>CM: set_on_frame_callback(_on_frame_captured)
    
    O->>RC: start()
    RC->>RC: Thread(target=_consume_loop).start()
    
    O->>D: start()
    D->>D: Thread(target=_display_loop).start()
```

---

## Sequence Diagram - Capture và Publish Frame

```mermaid
sequenceDiagram
    participant W as Webcam
    participant CT as Capture Thread
    participant O as Orchestrator
    participant DP as DriverPublisher
    participant SP as SeatbeltPublisher
    participant RMQ as RabbitMQ
    participant DQ as driver.frames
    participant SQ as seatbelt.frames

    loop Mỗi frame
        W->>CT: cap.read() → BGR frame
        CT->>CT: cv2.imencode(".jpg") → JPEG bytes
        CT->>CT: Lưu latest_frame, latest_jpeg (lock)
        CT->>O: on_frame_callback(jpeg, frame_id, timestamp)
        
        O->>DP: publish(jpeg, metadata)
        DP->>RMQ: basic_publish("adas.exchange", "driver.frame", jpeg, headers)
        RMQ->>DQ: driver.frames ← frame

        alt now - last >= SEATBELT_FRAME_INTERVAL
            O->>SP: publish(jpeg, metadata)
            SP->>RMQ: basic_publish("adas.exchange", "seatbelt.frame", jpeg, headers)
            RMQ->>SQ: seatbelt.frames ← frame
        end
    end
```

---

## Sequence Diagram - Nhận và hiển thị kết quả AI

```mermaid
sequenceDiagram
    participant RMQ as RabbitMQ
    participant RC as ResultConsumer Thread
    participant D as Display Thread
    participant CV as OpenCV Window

    RMQ->>RC: driver.result → _on_driver_message(body)
    RC->>RC: json.loads → DriverResultMessage
    RC->>RC: latest_driver_result = result (lock)
    RC->>D: update_driver_result(result)
    D->>D: _driver_result = result (lock)

    RMQ->>RC: seatbelt.result → _on_seatbelt_message(body)
    RC->>RC: json.loads → SeatbeltResultMessage
    RC->>RC: latest_seatbelt_result = result (lock)
    RC->>D: update_seatbelt_result(result)
    D->>D: _seatbelt_result = result (lock)

    loop ~30 FPS
        D->>CT: latest_frame (lock)
        D->>D: _draw_hud(frame)
        Note over D: Sleepy: YES/NO<br/>Seatbelt: YES/NO<br/>FPS: xx.x
        D->>CV: cv2.imshow("ADAS Monitor", frame)
    end
```

---

## Luồng hiển thị - Display Loop

```mermaid
flowchart TD
    A[Display Thread Start] --> B[cv2.namedWindow]
    B --> C[Resize window 960x640]
    C --> D{Vòng lặp}
    D --> E[Lấy latest_frame từ CameraManager]
    E --> F{Frame != None?}
    F -->|No| G[Tạo blank frame + text 'Waiting...']
    F -->|Yes| H[Gọi _draw_hud]
    H --> I[Đọc kết quả driver + seatbelt]
    I --> J[Vẽ overlay text lên frame]
    J --> K[cv2.imshow]
    G --> K
    K --> L[cv2.waitKey 1ms]
    L --> M{Phím q hoặc ESC?}
    M -->|Yes| N[Dừng vòng lặp]
    M -->|No| O[Tính display FPS]
    O --> P{Sleep để duy trì 30 FPS}
    P --> D
    N --> Q[cv2.destroyAllWindows]
    Q --> R[Display Thread Stop]
```

---

## Luồng Camera Capture - Chi tiết

```mermaid
flowchart TD
    A[Capture Thread Start] --> B{Mở camera thành công?}
    B -->|No| C[Sleep 1s, thử lại]
    C --> B
    B -->|Yes| D{Vòng lặp chính}
    D --> E{Camera còn mở?}
    E -->|No| F[Thử reconnect]
    F --> G{Reconnect OK?}
    G -->|No| C
    G -->|Yes| D
    E -->|Yes| H[cap.read → frame]
    H --> I{Đọc thành công?}
    I -->|No| D
    I -->|Yes| J[cv2.imencode → JPEG]
    J --> K{Encode OK?}
    K -->|No| D
    K -->|Yes| L[Lưu frame + JPEG vào lock]
    L --> M[Có callback đăng ký?]
    M -->|Yes| N[Gọi callback - non-blocking]
    M -->|No| O[Cập nhật FPS]
    N --> O
    O --> P{stop_event set?}
    P -->|Yes| Q[Thoát]
    P -->|No| D
```

---

## Overlay HUD - Chi tiết hiển thị

```
┌────────────────────────────────────────────────┐
│ ████████████████████████                        │
│ █ Sleepy : NO        █  ← dòng 1 (y=30)        │
│ ████████████████████████                        │
│ ████████████████████████                        │
│ █ Seatbelt : YES     █  ← dòng 2 (y=60)        │
│ ████████████████████████                        │
│ ████████████████████████                        │
│ █ FPS : 29.5         █  ← dòng 3 (y=90)        │
│ ████████████████████████                        │
│                                                 │
│                                                 │
│              [Luồng camera]                     │
│                                                 │
│                                                 │
└────────────────────────────────────────────────┘
```

**Chi tiết overlay:**

- Nền đen (`0,0,0`), chữ trắng (`255,255,255`).
- Font: `cv2.FONT_HERSHEY_SIMPLEX`, scale 0.6, thickness 2.
- Mỗi dòng cách nhau 30px theo chiều dọc.
- Dữ liệu lấy từ `ResultConsumer` latest result (thread-safe lock).

---

## Tương tác giữa các thread

```mermaid
graph LR
    subgraph "Thread Communication"
        CT[Capture Thread]
        RT[Result Consumer Thread]
        DT[Display Thread]
        MT[Main Thread - FastAPI]
    end

    subgraph "Shared State (Lock)"
        LF[latest_frame]
        LJ[latest_jpeg]
        FI[frame_id]
        TS[timestamp]
        FS[fps]
        DR[driver_result]
        SR[seatbelt_result]
    end

    CT -->|write| LF
    CT -->|write| LJ
    CT -->|write| FI
    CT -->|write| TS
    CT -->|write| FS
    RT -->|write| DR
    RT -->|write| SR
    DT -->|read| LF
    DT -->|read| DR
    DT -->|read| SR
    MT -->|read| LJ
    MT -->|read| FI
    MT -->|read| TS
    MT -->|read| FS
```

---

## Ghi chú

- Camera-Service **không có sliding window** - đây là logic của Driver-Service.
- Camera-Service **không có object detection** - đây là logic của Seatbelt-Service.
- Camera-Service **không tính EAR** - đây là logic của Driver-Service.
- Mọi giá trị hiển thị trên overlay đến từ kết quả được publish bởi các dịch vụ AI.
