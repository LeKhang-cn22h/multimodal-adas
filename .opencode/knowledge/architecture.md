# Kiến trúc tổng thể — MULTIMODAL-ADAS

## Nguyên tắc

- **ADR-006 (2026-07-11)**: camera-service được gộp vào driver-service.
  Driver-service giờ đảm nhận CẢ mở webcam VÀ toàn bộ pipeline AI.
  Không còn camera-service độc lập.
- Mỗi service trong `services/` là 1 FastAPI app độc lập, có Dockerfile riêng,
  chạy trong container riêng, giao tiếp qua HTTP (REST) nội bộ trong docker
  network định nghĩa ở `docker-compose.yml`.
- Không service nào được import code trực tiếp từ service khác (không share
  code qua `sys.path`, không mount chung volume code).

## Luồng dữ liệu chính (Driver fatigue detection)

```
driver-service
  │
  ├── 1. Background thread mở webcam (cv2.VideoCapture)
  │      └── encode JPEG, giữ latest_jpeg trong RAM
  │
  ├── 2. Function call trực tiếp (KHÔNG RabbitMQ, KHÔNG HTTP)
  │      latest_jpeg → FatigueDetector.process()
  │         ├── FaceLandmarkerService.detect()
  │         ├── FeatureService.extract() → 40 features
  │         └── IClassifier.classify() → ClassificationResult
  │
  └── 3. Publish kết quả qua RabbitMQ
         driver.result → consumer bên ngoài (hệ thống cảnh báo ADAS)
```

## Layered Architecture áp dụng cho MỌI service Python trong `services/`

```
app/
├── api/            # HTTP layer: nhận request, gọi service, trả response.
│                   #   KHÔNG tính toán, KHÔNG gọi AI trực tiếp.
├── core/           # config.py, logging_config.py, dependencies.py (DI wiring)
├── models/         # (nếu có ORM/DB models)
├── repositories/   # truy xuất/lưu trạng thái (kể cả in-memory, kể cả DB thật)
├── schemas/        # Pydantic request/response contracts
├── services/       # business logic + gọi ra ngoài (HTTP client, AI model...)
├── utils/          # pure function thuần toán học, KHÔNG I/O, KHÔNG network
└── main.py         # entry point DUY NHẤT, Composition Root (DI wiring)
```

Quy tắc phụ thuộc: `api -> services -> repositories`, `services -> utils`.
Không được phụ thuộc ngược (`utils` không được import `services`).