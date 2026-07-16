# FEAT-highlevel-model-test: Offline evaluation test cho 4 model

## Thuộc Requirement
[REQ-highlevel-model-test](../requirements/REQ-highlevel-model-test.md)

## Service
**driver-service** — thêm 1 file test mới `tests/test_highlevel_models.py`.
Không thay đổi code production, không ảnh hưởng service khác.

## Mô tả chức năng

Feature này tạo 1 script test offline, chạy độc lập (không cần RabbitMQ,
webcam, FastAPI), thực hiện:

1. **Parse ground truth** từ tên file trong `highlevel/`:
   - `eyeopen` / `eyeclose`
   - `glass` / `noglass`
   - `face` / `noface`
   - `yawn` / `noyawn`
   - `seatbelt` / `noseatbelt`

2. **Load 4 model**:
   - Eye CNN (`eye_state_model.pt`)
   - Mouth CNN (`mouth_state_model.pt`)
   - Seatbelt YOLO (`best.pt`)
   - Face Detection (YOLO face hoặc MediaPipe — chọn model có sẵn, đơn giản nhất)

3. **Chạy inference pipeline** cho từng ảnh:
   ```
   Ảnh → Face Detection → Nếu FACE:
                              ├── EyeCropper → Eye CNN → OPEN/CLOSED
                              └── MouthCropper → Mouth CNN → YAWN/NO_YAWN
                           → SeatbeltDetector → ON/OFF
   ```

4. **So sánh prediction vs ground truth**, tính accuracy cho từng model.

5. **Phân tích chi tiết**:
   - Eye CNN: accuracy breakdown theo `glass` vs `noglass`.
   - Mouth CNN: accuracy khi `face` vs `noface` (khi noface → luôn expect NO_YAWN).
   - In confusion matrix dạng text table.

6. **In báo cáo tổng hợp**: accuracy từng model, thời gian chạy, số lượng
   ảnh đã xử lý.

## Acceptance Criteria
| # | Tiêu chí |
|---|---------|
| AC-1 | Test chạy `pytest tests/test_highlevel_models.py -s` thành công |
| AC-2 | Load được cả 4 model không lỗi |
| AC-3 | Parse đúng ground truth từ 1002 tên file |
| AC-4 | Eye CNN accuracy được tính riêng cho ảnh có face |
| AC-5 | Mouth CNN accuracy được tính, frame `noface` skip hoặc expect NO_YAWN |
| AC-6 | Seatbelt accuracy tính trên toàn bộ 1002 ảnh |
| AC-7 | Face Detection accuracy tính trên toàn bộ 1002 ảnh |
| AC-8 | Output có confusion matrix text table cho từng model |
| AC-9 | Output có breakdown Eye accuracy theo glass/noglass |
| AC-10 | Tổng runtime in ra cuối test |

## Độ ưu tiên
**P1** — cần thiết để đánh giá chất lượng model trước khi tích hợp vào
pipeline thật, nhưng không block các tính năng production khác.

## Phụ thuộc
- Các model files phải tồn tại trong `app/models/` (đã có sẵn).
- Các class `EyeClassifier`, `MouthClassifier`, `Predictor`, `EyeCropper`,
  `MouthCropper`, `SeatbeltDetector` đã có trong `app/services/`.
- Face detection: `FaceLandmarkerService` (MediaPipe) hoặc YOLO face model
  — chọn 1, ưu tiên model đã có sẵn và đơn giản nhất để tích hợp.
