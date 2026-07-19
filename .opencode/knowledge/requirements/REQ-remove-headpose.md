# REQ-remove-headpose: Loại bỏ Head Pose khỏi Pipeline Drowsiness Detection

## 1. Actor
- **Hệ thống ADAS**: consumer nhận kết quả từ `driver.result` (không thay đổi).
- **Developer**: người chạy demo (`run_webcam_with_controls.py`, `run_video_with_controls.py`, `run_video.py`).
- **Tài xế (end-user)**: nhìn thấy overlay trạng thái trên màn hình demo.

## 2. Mục tiêu
Loại bỏ **hoàn toàn** Head Pose (yaw/pitch/roll) khỏi pipeline `DrowsinessDetector` — pipeline overlay real-time chính của project.

Lý do nghiệp vụ:
- Hệ thống chạy trên webcam monocular (2D), không có camera depth.
- solvePnP / head pose estimation cho webcam không ổn định — pitch dao động lớn gây false alarm.
- Bài toán chỉ cần phát hiện **buồn ngủ** (eye closure + yawn), không cần theo dõi hướng nhìn.

## 3. Ngữ cảnh
- **Pipeline hiện tại**: `DrowsinessDetector` (trong `app/services/drowsiness_detector.py`) dùng `FaceLandmarker` → `DriverSelector` → `EyeCropper`/`MouthCropper` → `Predictor` (CNN) → `GeometricVerifier` → `EyeStateBuffer`/`MouthStateBuffer` → `DrowsinessRuleEngine`. Overlay vẫn hiển thị Yaw/Pitch, nhưng Rule Engine đã không dùng Head Pose để quyết định (comment ghi "Không còn sử dụng Head Pose").
- **DrowsinessLevel enum** hiện có 6 giá trị nhưng thực tế chỉ 4 được dùng: `NORMAL`, `NO_FACE`, `DROWSY_MILD`, `DROWSY_SEVERE`. `LOOKING_AWAY` và `YAWNING` là dead code.
- **Pipeline B** (`FatigueDetector` + 40-feature RF classifier) không được người dùng sử dụng — sẽ được xử lý dependency khi xóa `headpose.py`.
- Demo scripts (`run_webcam_with_controls.py`, `run_video_with_controls.py`, `run_video.py`) đều dùng Pipeline A.

## 4. Acceptance Criteria
1. **AC1**: `DrowsinessDetector.process()` không còn compute hay hiển thị yaw/pitch/roll.
2. **AC2**: `DrowsinessLevel` enum chỉ còn 4 giá trị: `NORMAL`, `DROWSY`, `NO_FACE`, `FACE_DETECTED_BUT_INVALID`.
3. **AC3**: `DrowsinessRuleEngine.decide()` nhận `face_detected`, `crop_valid`, `eye_buffer_result`, `mouth_buffer_result` và trả về đúng 1 trong 4 trạng thái trên.
4. **AC4**: Overlay trên frame chỉ hiển thị Eye, Mouth, State — không còn Yaw/Pitch/HeadPose/Looking Away.
5. **AC5**: File `app/utils/headpose.py` bị xóa hoàn toàn.
6. **AC6**: Không còn bất kỳ import, biến, hay logic nào liên quan đến `extract_head_pose`, `yaw`, `pitch`, `roll`, `HeadPose`, `headpose` trong toàn bộ Pipeline A.
7. **AC7**: Demo scripts (`run_webcam_with_controls.py`, `run_video_with_controls.py`, `run_video.py`) chạy được ngay sau refactor, không lỗi import.
8. **AC8**: Các component KHÔNG bị ảnh hưởng: `EyeCropper`, `MouthCropper`, `Predictor`, `EyeStateBuffer`, `MouthStateBuffer`, `GeometricVerifier`, `DriverSelector`, `SafetyMonitor`, `SeatbeltDetector`.
9. **AC9**: Không dead code, không import thừa, không comment code cũ, không placeholder.

## 5. Ràng buộc
- **Không thay đổi** API public (`GET /health`, `GET /stats`, `GET /frame`).
- **Không thay đổi** logic của `EyeStateBuffer`, `MouthStateBuffer`, `GeometricVerifier`, `DriverSelector`.
- **Không thay đổi** schema `driver.result` (nếu pipeline B được sửa thì phải giữ tương thích).
- Project phải chạy được ngay sau refactor (demo scripts hoạt động).

## 6. Service bị ảnh hưởng
- **driver-service** (port 8001) — service duy nhất bị ảnh hưởng.
- Các service khác (`lane-service`, `vehicle-service`, `frontend`) không liên quan.
