# FEAT-remove-headpose-utils-config: Xóa headpose.py & dọn config Head Pose

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-remove-headpose.md`

## Service
`driver-service`

## Mô tả chức năng
1. **Xóa file** `app/utils/headpose.py` hoàn toàn.
2. **Xóa threshold Head Pose** trong config:
   - `app/core/drowsiness_config.py`: xóa `yaw_threshold_deg`, `pitch_threshold_deg`.
   - `app/core/config.py`: xóa `HEAD_POSE_PITCH_THRESHOLD`, `HEAD_POSE_YAW_THRESHOLD`.
3. **Xử lý dependency**: `app/services/feature_service.py` import `extract_head_pose` từ `headpose.py` — phải sửa để không import nữa, hardcode `yaw=0.0, pitch=0.0, roll=0.0` (giữ nguyên cấu trúc 40-feature cho tương thích, nhưng giá trị luôn = 0).
4. **Xóa yaw/pitch/roll khỏi test data**: `tests/test_fatigue.py` dòng 99.

## Acceptance Criteria
- AC1: File `app/utils/headpose.py` không tồn tại.
- AC2: `app/core/drowsiness_config.py` không còn field `yaw_threshold_deg`, `pitch_threshold_deg`.
- AC3: `app/core/config.py` không còn `HEAD_POSE_PITCH_THRESHOLD`, `HEAD_POSE_YAW_THRESHOLD`.
- AC4: `app/services/feature_service.py` không import từ `app.utils.headpose`, `yaw/pitch/roll` luôn = 0.0 trong `roots` và `_NEUTRAL_ROOTS`.
- AC5: `app/services/feature_engineering.py` vẫn compile được (buffer vẫn nhận giá trị 0.0).
- AC6: `app/services/fatigue_detector.py` không còn `"yaw": 0.0, "pitch": 0.0, "roll": 0.0` trong `_EMPTY_FEATURES`.
- AC7: `tests/test_fatigue.py` không còn reference đến `yaw`, `pitch`, `roll`.
- AC8: Toàn bộ project không còn import `extract_head_pose` hoặc `from app.utils.headpose`.

## Độ ưu tiên
**P0** — Xóa file nguồn là bước cuối cùng để đảm bảo không còn dependency.

## Phụ thuộc
- `FEAT-remove-headpose-detector` (phải xong trước để đảm bảo không còn ai import `headpose`).
