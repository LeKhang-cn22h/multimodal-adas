# Cấu trúc dự án - Seatbelt-Service

## Cây thư mục

```
seatbelt_service/
├── Dockerfile                  # Container build
├── main.py                     # Entry point: uvicorn.run
├── main_detection.py           # Standalone test (giữ nguyên)
├── requirements.txt
├── best_1.pt                   # YOLO model (không commit git)
│
├── app/
│   ├── main.py                 # FastAPI + lifespan
│   ├── api/seatbelt.py         # Routes
│   ├── core/config.py          # Settings
│   ├── messaging/              # RabbitMQ layer
│   │   ├── connection.py
│   │   ├── publisher.py
│   │   ├── consumer.py
│   │   └── orchestrator.py
│   ├── services/
│   │   ├── seatbelt_detector.py  # YOLO logic (GIỮ NGUYÊN)
│   │   └── detector_instance.py  # Singleton
│   ├── schemas/seatbelt.py     # API schemas
│   └── utils/logger.py         # Logger
│
├── documents/                  # Tài liệu
│   ├── requirement.md
│   ├── features.md
│   ├── tech_solution.md
│   ├── logic_ai.md
│   ├── implementation.md
│   └── testing.md
├── memory/                     # Bộ nhớ AI Agent
├── knowledge-base/             # Kiến thức ổn định
└── tests/
```

## Layer architecture

```
api/          → Interface Adapters (REST)
messaging/    → Infrastructure (RabbitMQ)
services/     → Application Services (YOLO)
core/         → Configuration
schemas/      → API DTOs
utils/        → Shared utilities
```
