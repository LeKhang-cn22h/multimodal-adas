# FEAT-remove-headpose-detector: Loại bỏ Head Pose khỏi DrowsinessDetector

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-remove-headpose.md`

## Service
`driver-service` — file `app/services/drowsiness_detector.py`

## Mô tả chức năng
Refactor `DrowsinessDetector` để:

1. **Pipeline mới** (cập nhật docstring):
   ```
   Frame → FaceLandmarker → DriverSelector → Crop Eyes/Mouth
   → Eye/Mouth CNN → GeometricVerifier → Eye/Mouth Buffer → RuleEngine → Overlay
   ```

2. **`_draw_overlay()`**: Xóa hoàn toàn phần hiển thị Yaw/Pitch. Chỉ giữ Eye, Mouth, State. Đổi logic warning border để dùng `DROWSY` thay vì `DROWSY_SEVERE`.

3. **`process()`**: 
   - Tính toán `face_detected` (có landmarks hay không) và `crop_valid` (crop được cả 3 ROI).
   - Truyền `face_detected` và `crop_valid` vào `rule_engine.decide()` theo signature mới.
   - Pipeline không còn bước Head Pose nào.

4. **Import clean-up**: Không import các module/class liên quan đến head pose.

## Acceptance Criteria
- AC1: Docstring pipeline diagram không còn nhắc đến Head Pose.
- AC2: `_draw_overlay()` không có `pose_result` parameter, không hiển thị Yaw/Pitch text.
- AC3: `_draw_overlay()` dùng `DROWSY` (không phải `DROWSY_SEVERE`) cho warning border.
- AC4: `process()` tính `face_detected` và `crop_valid`, truyền vào `rule_engine.decide(face_detected, crop_valid, eye_buffer_result, mouth_buffer_result)`.
- AC5: Khi `crop_valid=False`, `eye_buffer_result` và `mouth_buffer_result` là `None`.
- AC6: Không còn biến `pose_result` ở bất kỳ đâu trong file.
- AC7: Demo scripts (`run_webcam_with_controls.py`, `run_video_with_controls.py`, `run_video.py`) chạy không lỗi với DrowsinessDetector mới.

## Độ ưu tiên
**P0** — Đây là file chính của pipeline A.

## Phụ thuộc
- `FEAT-remove-headpose-drowsiness-level` (enum mới)
- `FEAT-remove-headpose-rule-engine` (signature `decide()` mới)
