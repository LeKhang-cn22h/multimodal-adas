# FEAT-feature-extraction: MAR, HeadPose, PERCLOS Extraction

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-drowsiness-detection.md` — AC-2 (Feature Extraction Layer)

## Service
**driver-service** — tạo mới `utils/mar.py`, `utils/headpose.py`, `utils/perclos.py`, `services/feature_service.py`

## Mô tả chức năng

Implement 3 feature extractors còn thiếu (MAR, HeadPose, PERCLOS) dưới dạng pure function trong `utils/`, sau đó tạo 1 `FeatureService` trong `services/` để orchestrate việc gọi tất cả 4 feature (EAR có sẵn + 3 mới).

### Các pure function mới trong `utils/`

| File | Hàm | Input | Output | Ghi chú |
|---|---|---|---|---|
| `ear.py` | `calculate_ear(landmarks, indices)` | landmarks + 6 indices | float | **Giữ nguyên**, không sửa |
| `mar.py` | `calculate_mar(landmarks)` | landmarks (478) | float | Dùng Face Landmarker mouth topology |
| `headpose.py` | `extract_head_pose(transformation_matrix)` | np.ndarray (4x4) | `(yaw, pitch, roll)` độ | Decompose rotation → Euler angles |
| `perclos.py` | `update_perclos(ear_value, window_size, ear_threshold)` | float + state | `float` (0-100%) | **Có state** → nên là class `PERCLOSCalculator` trong `services/` thay vì `utils/` |

### `FeatureService` trong `services/feature_service.py`

Orchestrate việc trích xuất toàn bộ 6 features từ 1 frame:
- Nhận: `FaceLandmarkerResult` (từ `FaceLandmarkerService`)
- Gọi: `calculate_ear()`, `calculate_mar()`, `extract_head_pose()`, `PERCLOSCalculator.update()`
- Trả về: `FeatureVector` (dataclass/Pydantic với 6 fields)

## Acceptance Criteria

- [ ] **AC-F2.1**: `utils/mar.py` chứa pure function `calculate_mar(landmarks) -> float`, dùng đúng Face Landmarker mouth indices (môi trên/dưới, khóe miệng). Có docstring + type hint đầy đủ
- [ ] **AC-F2.2**: `utils/headpose.py` chứa pure function `extract_head_pose(transformation_matrix: np.ndarray) -> tuple[float, float, float]` trả về `(yaw, pitch, roll)` độ. Dùng `cv2.decomposeProjectionMatrix` hoặc công thức Euler từ rotation submatrix
- [ ] **AC-F2.3**: `services/perclos_calculator.py` (hoặc `utils/perclos.py` nếu giữ pure) chứa class `PERCLOSCalculator` với: sliding window N giây (configurable), method `update(ear: float, timestamp: float) -> float` trả về PERCLOS %, mắt đóng = EAR < threshold
- [ ] **AC-F2.4**: `services/feature_service.py` chứa `FeatureService` với method `extract(landmarker_result: FaceLandmarkerResult) -> FeatureVector`. Nếu `face_detected=False` → trả về `FeatureVector` với tất cả field = 0.0
- [ ] **AC-F2.5**: `FeatureVector` là Pydantic model hoặc dataclass trong `models/` hoặc `schemas/` chứa: `ear: float`, `perclos: float`, `mar: float`, `yaw: float`, `pitch: float`, `roll: float`
- [ ] **AC-F2.6**: Các hàm trong `utils/` pass unit test với dữ liệu landmarks giả lập (không cần model thật)
- [ ] **AC-F2.7**: Mouth indices cho MAR được định nghĩa rõ ràng trong `utils/mar.py` dưới dạng constant (VD: `MOUTH_OUTER = [...]`, `MOUTH_INNER = [...]`), dựa trên Face Landmarker 478-point topology

## Độ ưu tiên
**P0** — Không có features thì không có pipeline. Phụ thuộc vào FEAT-landmark-refactor.

## Phụ thuộc
- **FEAT-landmark-refactor**: Cần `FaceLandmarkerResult` làm input cho `FeatureService.extract()`
