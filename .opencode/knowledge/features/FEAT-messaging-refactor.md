# FEAT-messaging-refactor: Dời messaging/ vào services/

## Thuộc Requirement
Không thuộc REQ cụ thể — đây là technical debt cleanup từ kiến trúc hiện tại.

## Service
**driver-service** — `app/messaging/` nằm ngoài Layered Architecture chuẩn (`api/ → services/ → repositories/`). Camera-service đã bị xoá (ADR-006) nên không còn áp dụng.

## Mô tả chức năng

Hiện tại driver-service có thư mục `app/messaging/` chứa logic kết nối RabbitMQ (`connection.py`, `publisher.py`, `orchestrator.py`). Thư mục này nằm ngoài Layered Architecture chuẩn — vi phạm quy ước trong `.opencode/knowledge/architecture.md` và `.opencode/knowledge/conventions.md`.

> **ADR-006 (2026-07-11)**: camera-service đã được gộp vào driver-service. `messaging/consumer.py` (FrameConsumer) đã bị xoá. Phạm vi refactor này chỉ còn áp dụng cho:
> - `messaging/connection.py` → `services/messaging_connection.py`
> - `messaging/publisher.py` → `services/result_publisher.py` (chỉ còn `ResultPublisher`, không còn `FramePublisher`)
> - `messaging/orchestrator.py` → `services/messaging_orchestrator.py`

Đồng thời, logic DI wiring trong orchestrator nên được tách riêng — phần wiring thuộc về `app/core/dependencies.py` hoặc `app/main.py` lifespan (Composition Root), phần business logic (start/stop camera, worker thread, publisher) thuộc về `services/`.

## Acceptance Criteria

- [ ] **AC-M1**: Tất cả file trong `app/messaging/` được dời vào `app/services/` với tên rõ ràng (`messaging_connection.py`, `result_publisher.py`, `messaging_orchestrator.py`)
- [ ] **AC-M2**: Import trong toàn bộ service được cập nhật để reflect đường dẫn mới
- [ ] **AC-M3**: `app/main.py` (lifespan) cập nhật import path, không thay đổi behavior
- [ ] **AC-M4**: DI wiring (khởi tạo `CameraCaptureService`, `FeatureService`, `FatigueDetector`, classifier, etc.) được tách khỏi orchestrator, chuyển vào `app/core/dependencies.py` hoặc `app/main.py` lifespan
- [ ] **AC-M5**: Sau refactor, service vẫn start/shutdown đúng (model load → camera start → worker thread → RabbitMQ connect)
- [ ] **AC-M6**: Sau refactor, `GET /health`, `GET /stats`, `GET /frame` vẫn hoạt động

## Độ ưu tiên

**P2** — Không blocker cho bất kỳ feature P0/P1 nào. Làm sau khi toàn bộ pipeline drowsiness detection hoàn tất. Tuy nhiên PHẢI làm trước khi coi project là "production-ready", vì vi phạm layered architecture.

## Phụ thuộc

- **FEAT-service-merge** (đã hoàn tất): xoá `consumer.py`, gộp camera-service. Scope của refactor này phụ thuộc vào kết quả merge.
- Không phụ thuộc feature nào khác.

## Ghi chú

- ADR-006 đã supersede ADR-003 phần giao tiếp frame nội bộ. Phần "publish driver.result" vẫn giữ nguyên → `ResultPublisher` là file duy nhất trong `messaging/` có business value thật sự.
- Camera-service không còn tồn tại → AC-M7 cũ (dời messaging của camera-service) đã bị xoá khỏi scope.
