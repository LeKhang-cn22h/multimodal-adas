# Quy ước code - Camera-Service

## Clean Architecture

Camera-Service tuân theo kiến trúc Clean Architecture với 3 layer chính:

```
┌─────────────────────────────────────┐
│         Interface Adapters          │
│  api/          (REST routes)        │
│  schemas/      (API DTOs)           │
└──────────────┬──────────────────────┘
               │ depends on
┌──────────────▼──────────────────────┐
│       Application Services          │
│  services/     (use cases)          │
│  messaging/    (infrastructure)     │
└──────────────┬──────────────────────┘
               │ depends on
┌──────────────▼──────────────────────┐
│            Domain                   │
│  models/      (domain entities)     │
│  core/        (configuration)       │
└─────────────────────────────────────┘
```

**Quy tắc dependency**: Layer ngoài phụ thuộc vào layer trong. Layer trong không biết layer ngoài.

## Naming Convention

### Module / File
- **snake_case**: Tất cả file và thư mục.
- Ví dụ: `camera_manager.py`, `test_display.py`.

### Class
- **PascalCase**: Tất cả class.
- Ví dụ: `CameraManager`, `FramePublisher`, `RabbitMQConnectionManager`.

### Function / Method
- **snake_case**: Tất cả function và method.
- Ví dụ: `get_settings()`, `set_on_frame_callback()`, `_capture_loop()`.

### Biến
- **snake_case** cho biến thông thường.
- **UPPER_CASE** cho constants.
- Prefix `_` cho private/protected: `self._latest_frame`.
- Ví dụ: `DRIVER_FRAMES`, `_stop_event`, `frame_id`.

### Constants
- Định nghĩa trong class hoặc module-level.
- Ví dụ: `FramePublisher.EXCHANGE = "adas.exchange"`.

## Type Hints

**Bắt buộc** sử dụng type hints cho tất cả function signatures:

```python
def publish(self, jpeg_bytes: bytes, metadata: FrameMessage) -> bool:
    ...

def get_stats(self) -> dict:
    ...
```

Sử dụng `Optional[Type]` thay vì `Type | None` cho Python < 3.10 (hỗ trợ runtime).

## Docstrings

Sử dụng Google-style docstrings:

```python
def process(self, jpeg_bytes: bytes, frame_id: int, timestamp: float) -> dict:
    """Process a single JPEG frame.

    Args:
        jpeg_bytes: Raw JPEG frame bytes.
        frame_id: Sequential frame identifier.
        timestamp: Unix timestamp from camera.

    Returns:
        dict with keys: frame_id, timestamp, sleepy, confidence.
    """
```

## Thread Safety

Tất cả dữ liệu dùng chung giữa các thread phải được bảo vệ:

```python
# ĐÚNG
with self._lock:
    self._latest_jpeg = jpeg_bytes

# SAI
self._latest_jpeg = jpeg_bytes  # không có lock
```

## Error Handling

- **Không nuốt exception**: Luôn log exception trước khi xử lý.
- **Graceful degradation**: Nếu publish thất bại, không crash - chỉ log warning.
- **Retry cho transient errors**: RabbitMQ connection error → retry với backoff.

```python
# ĐÚNG
try:
    self._channel.basic_publish(...)
    return True
except (AMQPConnectionError, AMQPChannelError) as exc:
    logger.warning("Publish failed: %s", exc)
    return False

# SAI
self._channel.basic_publish(...)  # có thể throw, không xử lý
```

## Logging

Sử dụng structured logger với format:
```
%(asctime)s | %(levelname)-8s | %(name)s | %(message)s
```

Level guidelines:
- **DEBUG**: Thông tin chi tiết (vd: "Received frame 42")
- **INFO**: Sự kiện quan trọng (vd: "Camera opened 640x480")
- **WARNING**: Vấn đề có thể phục hồi (vd: "Camera disconnected, reconnecting")
- **ERROR**: Lỗi nghiêm trọng (vd: "Reconnect failed")

## Import Order

1. Standard library imports
2. Third-party imports
3. Local application imports

```python
import threading
import time

import cv2
import numpy as np

from app.core.config import get_settings
from app.utils.logger import get_logger
```

## Environment Variables

Tất cả cấu hình qua environment variables. KHÔNG hardcode:

```python
# ĐÚNG
CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))

# SAI
CAMERA_INDEX = 0  # hardcoded
```

## Các nguyên tắc khác

- **Single Responsibility**: Mỗi class chỉ có một lý do để thay đổi.
- **Open/Closed**: Mở để mở rộng (thêm FramePublisher mới), đóng để sửa đổi.
- **Composition over Inheritance**: Dùng composition (Orchestrator chứa Publishers, Consumer) thay vì kế thừa.
