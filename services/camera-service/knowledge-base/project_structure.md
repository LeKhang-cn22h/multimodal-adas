# Cấu trúc dự án - Camera-Service

## Tổng quan

Camera-Service tuân theo kiến trúc Clean Architecture với các layer được phân tách rõ ràng.

## Cây thư mục

```
camera-service/
│
├── Dockerfile                  # Container build
├── main.py                     # Entry point cho development (uvicorn.run)
├── requirements.txt            # Python dependencies
├── desktop_monitor.py          # [DEPRECATED] Desktop app cũ (HTTP-based)
├── README.md                   # Tổng quan dịch vụ
│
├── app/                        # Application code
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + lifespan management
│   │
│   ├── api/                    # Layer: Interface Adapters (REST API)
│   │   ├── __init__.py
│   │   └── camera.py           # Route handlers
│   │
│   ├── core/                   # Layer: Core configuration
│   │   ├── __init__.py
│   │   └── config.py           # Settings (env vars)
│   │
│   ├── messaging/              # Layer: Infrastructure (RabbitMQ)
│   │   ├── __init__.py
│   │   ├── connection.py       # Connection manager
│   │   ├── publisher.py        # Frame publisher
│   │   ├── consumer.py         # Result consumer
│   │   └── orchestrator.py     # Lifecycle orchestrator
│   │
│   ├── models/                 # Layer: Domain Models
│   │   ├── __init__.py
│   │   └── messages.py         # Message schemas (Pydantic)
│   │
│   ├── services/               # Layer: Use Cases / Application Services
│   │   ├── __init__.py
│   │   ├── camera_manager.py   # Camera capture service
│   │   ├── camera_manager_instance.py  # Singleton
│   │   └── display.py          # Display + overlay service
│   │
│   ├── schemas/                # Layer: API Schemas (DTOs)
│   │   ├── __init__.py
│   │   └── camera.py           # Response schemas (Pydantic)
│   │
│   └── utils/                  # Layer: Shared Utilities
│       ├── __init__.py
│       └── logger.py           # Structured logger
│
├── documents/                  # Tài liệu chính thức
│   ├── requirement.md
│   ├── features.md
│   ├── tech_solution.md
│   ├── logic_ai.md
│   ├── implementation.md
│   └── testing.md
│
├── memory/                     # Bộ nhớ dự án
│   ├── decisions.md
│   ├── changelog.md
│   ├── implementation_notes.md
│   ├── known_issues.md
│   ├── lessons_learned.md
│   └── development_log.md
│
├── knowledge-base/             # Kiến thức ổn định
│   ├── architecture.md
│   ├── api.md
│   ├── rabbitmq.md
│   ├── project_structure.md
│   ├── coding_guidelines.md
│   ├── ai_pipeline.md
│   ├── deployment.md
│   ├── configuration.md
│   ├── glossary.md
│   └── troubleshooting.md
│
└── tests/                      # Test files
    ├── __init__.py
    ├── conftest.py
    ├── test_models.py
    ├── test_display.py
    ├── test_connection.py
    ├── test_messaging.py
    └── test_camera_manager.py
```

## Giải thích từng thư mục

### `app/api/`
**Trách nhiệm**: REST API route handlers.
**Quy tắc**: Chỉ chứa route handlers. Không chứa business logic. Gọi đến service layer để xử lý.
**Ví dụ**: `GET /health` → đọc `camera_manager.is_running`.

### `app/core/`
**Trách nhiệm**: Cấu hình ứng dụng.
**Quy tắc**: Tất cả config từ environment variables. Không hardcode.
**Ví dụ**: `Settings` class với `CAMERA_INDEX`, `RABBITMQ_HOST`, v.v.

### `app/messaging/`
**Trách nhiệm**: Tất cả logic giao tiếp RabbitMQ.
**Quy tắc**: Code RabbitMQ không được viết trong `api/` hoặc `services/`.
**Ví dụ**: `FramePublisher`, `ResultConsumer`, `RabbitMQConnectionManager`.

### `app/models/`
**Trách nhiệm**: Domain models (Pydantic) cho message passing.
**Quy tắc**: Không chứa business logic, chỉ data validation.
**Ví dụ**: `FrameMessage`, `DriverResultMessage`, `SeatbeltResultMessage`.

### `app/services/`
**Trách nhiệm**: Business logic / Application services.
**Quy tắc**: Đây là nơi chứa logic chính của ứng dụng.
**Ví dụ**: `CameraManager` (capture logic), `DisplayOverlay` (display logic).

### `app/schemas/`
**Trách nhiệm**: API response schemas (DTOs).
**Quy tắc**: Tách biệt với domain models. API schemas có thể khác với internal models.
**Ví dụ**: `HealthResponse`, `CameraInfoResponse`, `CameraStatsResponse`.

### `app/utils/`
**Trách nhiệm**: Shared utilities (cross-cutting concerns).
**Quy tắc**: Không phụ thuộc vào business logic.
**Ví dụ**: `CameraLogger` - structured logging.

### `documents/`
**Trách nhiệm**: Tài liệu chính thức của dự án.
**Đối tượng**: Developer, PM, QA.
**Nội dung**: Yêu cầu, tính năng, giải pháp kỹ thuật, kiểm thử.

### `memory/`
**Trách nhiệm**: Bộ nhớ dài hạn cho AI Agent.
**Đối tượng**: AI Agent trong tương lai.
**Nội dung**: Quyết định, changelog, bài học, lỗi đã biết.

### `knowledge-base/`
**Trách nhiệm**: Kiến thức ổn định để AI Agent hiểu hệ thống.
**Đối tượng**: AI Agent.
**Nội dung**: Kiến trúc, API, deployment, cấu hình.

### `tests/`
**Trách nhiệm**: Unit tests và integration tests.
**Quy tắc**: Mỗi module có file test tương ứng.
**Công cụ**: pytest + pytest-mock.
