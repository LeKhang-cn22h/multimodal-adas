# REQ-highlevel-model-test: Đánh giá độ chính xác 4 model trên dataset highlevel

## 1. Actor
- **Developer / ML Engineer**: muốn biết accuracy của từng model trong pipeline
  driver-service khi chạy trên bộ dataset highlevel (1002 ảnh).
- **Hệ thống ADAS**: gián tiếp hưởng lợi từ việc đảm bảo chất lượng model
  trước khi deploy.

## 2. Mục tiêu
Viết 1 file test high-level (`tests/test_highlevel_models.py`) chạy toàn bộ
4 model của driver-service trên dataset `highlevel/`, so sánh kết quả dự
đoán với ground truth từ tên file, báo cáo accuracy (%) cho từng model.

Ngoài accuracy tổng, phân tích sâu:
- Eye model: accuracy khi có kính (`glass`) vs không kính (`noglass`).
- Mouth model: accuracy khi có face vs không có face.
- Seatbelt model: accuracy chung.

## 3. Ngữ cảnh
- **Dataset**: `services/driver-service/highlevel/` — 1002 ảnh JPEG,
  ground truth nằm trong tên file theo format:
  `{eye_state}_{glass}_{face}_{yawn}_{seatbelt}_{index}.jpg`
  - `eye_state`: `eyeopen` / `eyeclose`
  - `glass`: `glass` / `noglass`
  - `face`: `face` / `noface`
  - `yawn`: `yawn` / `noyawn`
  - `seatbelt`: `seatbelt` / `noseatbelt`
- **4 model cần đánh giá**:
  1. **Eye CNN** (`app/models/eye_state_model.pt`) — phân loại OPEN/CLOSED
  2. **Mouth CNN** (`app/models/mouth_state_model.pt`) — phân loại YAWN/NO_YAWN
  3. **Seatbelt YOLO** (`app/models/best.pt`) — phát hiện seatbelt ON/OFF
  4. **Face Detection** (`app/models/yolov8n-face.pt` hoặc MediaPipe
     `face_landmarker.task`) — phát hiện FACE/NO_FACE
- **Pipeline hiện tại**: `DrowsinessDetector` (dùng EyeCropper + MouthCropper
  + Predictor) và `SeatbeltDetector` là các component đã có sẵn trong
  `app/services/`.
- **Lưu ý**: `glass` KHÔNG phải là model riêng — nó là metadata để phân tích
  xem Eye CNN có hoạt động tốt khi tài xế đeo kính không. `face` là
  precondition: nếu `noface` thì Eye/Mouth model không thể cho kết quả hợp lệ.

## 4. Acceptance Criteria

| # | Tiêu chí | Cách đo |
|---|---------|---------|
| AC-1 | Test chạy được trên toàn bộ 1002 ảnh, không crash | Exit code 0, không exception |
| AC-2 | Báo cáo accuracy (%) cho Eye CNN (OPEN/CLOSED) | In ra % đúng/tổng, chỉ tính frame có `face` |
| AC-3 | Báo cáo accuracy (%) cho Mouth CNN (YAWN/NO_YAWN) | In ra % đúng/tổng, chỉ tính frame có `face` |
| AC-4 | Báo cáo accuracy (%) cho Seatbelt YOLO (ON/OFF) | In ra % đúng/tổng, tất cả frame |
| AC-5 | Báo cáo accuracy (%) cho Face Detection (FACE/NO_FACE) | In ra % đúng/tổng, tất cả frame |
| AC-6 | Phân tích Eye CNN theo điều kiện `glass` vs `noglass` | In accuracy riêng cho từng nhóm |
| AC-7 | Phân tích Mouth CNN theo điều kiện `face` vs `noface` | Frame `noface` → Mouth phải trả NO_YAWN |
| AC-8 | In confusion matrix cho từng model (nếu có ≥ 2 class) | Dạng text table |
| AC-9 | Tổng thời gian chạy test được in ra | Giây, hiển thị cuối output |

## 5. Ràng buộc
- File test đặt tại `services/driver-service/tests/test_highlevel_models.py`.
- Chạy được bằng `pytest tests/test_highlevel_models.py -s` từ thư mục
  `services/driver-service/`.
- Sử dụng đúng các class đã có trong `app/services/`:
  - `EyeClassifier` + `MouthClassifier` + `Predictor` (không viết lại
    inference code mới).
  - `SeatbeltDetector` cho seatbelt detection.
  - Face detection: dùng `FaceLandmarkerService` (MediaPipe) hoặc YOLO
    face model, tùy theo model nào đã có sẵn và dễ tích hợp hơn.
- Không được hardcode path — dùng `app/config.py` hoặc `pathlib` relative.
- Dataset đọc từ `highlevel/` cùng cấp với `tests/` (relative path
  `../highlevel/`).
- Không yêu cầu RabbitMQ, webcam, hay bất kỳ infrastructure nào khác.
- Test là **offline evaluation**, không phải real-time pipeline.

## 6. Service bị ảnh hưởng
- **driver-service** (port 8001): thêm file test mới, không thay đổi code
  production.
