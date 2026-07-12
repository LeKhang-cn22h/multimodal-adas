# Session 2026-07-05 — Driver Drowsiness Detection: Requirements → TS-landmark-refactor (implemented + tested)

## Đã làm

### 1. sync-context (camera-service + driver-service)
- Đọc toàn bộ code 2 service, đối chiếu với knowledge base
- Phát hiện 7 điểm lệch (port, messaging layer, RabbitMQ vs HTTP, stub files...)
- Báo cáo tại phiên làm việc

### 2. Requirement
- **Tạo** `.opencode/knowledge/requirements/REQ-drowsiness-detection.md` — Pipeline 3 tầng cho driver-service
- **Cập nhật** REQ theo 3 quyết định:
  1. Giữ Face Landmarker 478 (không Face Mesh), Head Pose từ `facial_transformation_matrixes`
  2. Dataset NTHU-DDD (Kaggle mirror), bao gồm tải + preprocess + train baseline
  3. Rule-based fallback PERCLOS 4 cấp cụ thể

### 3. ADR-004
- **Thêm** vào `decisions.md`: giữ Face Landmarker 478, dùng transformation matrix cho Head Pose (không solvePnP)

### 4. Feature
- **Tạo** 5 file FEAT trong `.opencode/knowledge/features/`:
  - `FEAT-landmark-refactor.md` (P0) — Tách Face Landmarker → service riêng
  - `FEAT-feature-extraction.md` (P0) — MAR, HeadPose, PERCLOS extraction
  - `FEAT-fatigue-classifier.md` (P0) — Rule-based pipeline + output schema
  - `FEAT-dataset-training.md` (P1) — Tải NTHU-DDD + train RF baseline
  - `FEAT-rf-integration.md` (P0) — Tích hợp RF với fallback

### 5. Tech Solution
- **Tạo** `.opencode/knowledge/tech-solutions/TS-landmark-refactor.md`
  - Định nghĩa `FaceLandmarkerService` + `FaceLandmarkerResult` (3 fields)
  - Xác nhận `transformation_matrix` là input cho Head Pose (ADR-004)
  - Làm rõ: KHÔNG dời `messaging/` → `services/` (track trong open-questions)
- **Tạo** `.opencode/knowledge/tech-solutions/TS-dataset-training.md`
  - NTHU-DDD Kaggle mirror, binary classifier → Fatigue Score 0-100
  - BACKWARD window cho PERCLOS feature, CENTERED window chỉ cho label smoothing
  - Split theo subject_id, confusion matrix + ROC + feature importance

### 6. Implement — TS-landmark-refactor (đã xác nhận)
- **Tạo mới**: `services/mediapipe_service.py` (172 lines) — `FaceLandmarkerService` + `FaceLandmarkerResult`
- **Sửa**: `services/fatigue_detector.py` — Bỏ import `mediapipe`, nhận `FaceLandmarkerService` qua constructor (DIP)
- **Sửa**: `messaging/orchestrator.py` — Tạo `FaceLandmarkerService`, inject, thêm `landmark_service` property
- **Sửa**: `api/fatigue.py` — `GET /health` dùng `orchestrator.landmark_service.is_loaded`

### 7. Test — driver-service
- **Cập nhật**: `tests/test_fatigue.py` — Fix constructor injection (mock `FaceLandmarkerService`), thêm 4 test mới
- **Tạo mới**: `tests/test_mediapipe_service.py` — 11 tests cho `FaceLandmarkerResult` + `FaceLandmarkerService`
- **Sửa**: `test_normal_eye` — Tọa độ landmarks sai (EAR≈1.0) → đúng (EAR≈0.24, verified bằng script)
- **Kết quả**: **25/25 PASS** (14 test_fatigue + 11 test_mediapipe_service)

## Quyết định quan trọng

| ADR | Ngày | Quyết định |
|---|---|---|
| ADR-004 | 2026-07-05 | Giữ Face Landmarker 478, Head Pose từ `facial_transformation_matrixes`, không solvePnP. Đã thêm vào `decisions.md`. |

## Câu hỏi còn mở

- **ADR-003 dời messaging/ vào services/**: Đã thêm vào `open-questions.md`. Cần Feature + TS riêng.

## Việc tiếp theo

1. `/implement .opencode/knowledge/tech-solutions/TS-dataset-training.md` — Pipeline tải NTHU-DDD + train RF
2. `/techsolution .opencode/knowledge/features/FEAT-feature-extraction.md` — MAR + HeadPose + PERCLOS (phụ thuộc TS-landmark-refactor đã xong)
3. Sau FEAT-feature-extraction → `/techsolution FEAT-fatigue-classifier` → `/implement`
