# FEAT-landmark-refactor: Tách Face Landmarker thành service riêng

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-drowsiness-detection.md` — AC-1 (Landmark Layer)

## Service
**driver-service** — tạo mới `services/mediapipe_service.py`, sửa `services/fatigue_detector.py`

## Mô tả chức năng

Tách logic gọi MediaPipe Face Landmarker ra khỏi `FatigueDetector` hiện tại thành một class riêng `FaceLandmarkerService` trong `services/mediapipe_service.py`. Feature này chỉ làm sạch kiến trúc, không thay đổi hành vi bên ngoài.

**Input**: JPEG bytes (từ RabbitMQ consumer hoặc bất kỳ caller nào)
**Output**: `FaceLandmarkerResult` dataclass/Pydantic chứa:
- `landmarks: list[NormalizedLandmark] | None` — 478 landmarks (None nếu không phát hiện mặt)
- `transformation_matrix: np.ndarray | None` — ma trận 4x4 cho Head Pose (None nếu không có)
- `face_detected: bool`

Trách nhiệm của `FaceLandmarkerService`:
- Load model `face_landmarker.task` **1 lần** khi khởi tạo
- Nhận numpy array (BGR), decode nếu cần, chuyển RGB, gọi `detect_for_video()`
- Trả về kết quả có cấu trúc rõ ràng (không trả raw MediaPipe object)
- Giải phóng model khi `close()`

## Acceptance Criteria

- [ ] **AC-F1.1**: `FaceLandmarkerService` nằm trong `services/mediapipe_service.py`, có constructor nhận `model_path: str`
- [ ] **AC-F1.2**: Class có method `detect(frame: np.ndarray, timestamp_ms: int) -> FaceLandmarkerResult`, che giấu toàn bộ chi tiết MediaPipe API
- [ ] **AC-F1.3**: `FaceLandmarkerResult` là Pydantic model hoặc dataclass, chứa `landmarks`, `transformation_matrix`, `face_detected`
- [ ] **AC-F1.4**: Model load 1 lần khi gọi `load_model()`, không load lại mỗi lần detect. Có method `close_model()` để giải phóng
- [ ] **AC-F1.5**: `FatigueDetector` hiện tại được refactor để dùng `FaceLandmarkerService` thay vì gọi MediaPipe trực tiếp. Hành vi hiện tại (EAR → sleepy bool) không thay đổi
- [ ] **AC-F1.6**: Nếu không phát hiện mặt → `landmarks=None`, `face_detected=False`, không throw exception
- [ ] **AC-F1.7**: `messaging/orchestrator.py` khởi tạo `FaceLandmarkerService` 1 lần, inject vào `FatigueDetector` qua constructor (DIP)

## Độ ưu tiên
**P0** — Đây là prerequisite cho mọi feature extraction khác (MAR, HeadPose, PERCLOS). Phải làm trước tiên để có interface rõ ràng.

## Phụ thuộc
Không phụ thuộc feature nào khác. Dựa trên code hiện có trong `fatigue_detector.py`.
