# REQ-merged-monitoring: Gộp Seatbelt Detection vào Driver-Service + Video File Input

## 1. Actor
- **Developer / QA Engineer**: Người chạy service trên máy local, chọn video
  file để kiểm tra đồng thời cả drowsiness detection và seatbelt detection.
- **Hệ thống ADAS (tương lai)**: Consumer nhận kết quả detection qua RabbitMQ
  `driver.result` và `seatbelt.result`.

## 2. Mục tiêu
Gộp pipeline seatbelt detection (YOLO) từ `seatbelt_service` vào chính
`driver-service` hiện có. Khi có video input từ máy local, service bật
đồng thời cả 2 model AI (MediaPipe drowsiness + YOLO seatbelt) trên cùng
từng frame, hiển thị kết quả overlay real-time.

## 3. Ngữ cảnh
- `driver-service` (`services/driver-service/`) đã có pipeline AI hoàn chỉnh:
  MediaPipe Face Landmarker → 40-feature extraction → RF/Rule-based
  classifier → publish `driver.result` qua RabbitMQ. Input hiện tại là
  webcam qua `CameraCaptureService`.
- `seatbelt_service` (`services/seatbelt_service/`) có YOLO model
  `best_1.pt` (7 classes, class_id=6 là seatbelt), hiện nhận frame qua
  RabbitMQ. Có script `main_detection.py` đã hỗ trợ video file + overlay.
- **ADR-006**: camera-service đã gộp vào driver-service. Giờ gộp tiếp
  seatbelt vào driver-service.
- **Yêu cầu**: input chuyển từ webcam sang video file local (người dùng
  chọn/nhập đường dẫn). Khi có input thì bật cả 2 model.

## 4. Acceptance Criteria
1. **Seatbelt trong driver-service**: Copy toàn bộ logic YOLO seatbelt
   detection từ `seatbelt_service` vào `driver-service` (file mới trong
   `app/services/` và thư mục model), không sửa code gốc của seatbelt_service.
2. **Không phá vỡ pipeline drowsiness**: Code AI hiện có của driver-service
   (MediaPipe, feature extraction, classifier) giữ nguyên, không sửa đổi
   logic detection.
3. **Video file input**: Service nhận đường dẫn video file local (qua CLI
   arg hoặc env var), đọc từng frame bằng OpenCV thay vì mở webcam.
4. **Dual-model inference**: Mỗi frame được xử lý qua CẢ 2 pipeline:
   - **Drowsiness**: MediaPipe → FeatureService → Classifier
   - **Seatbelt**: YOLO inference
   Hai model chạy tuần tự trên cùng frame, không xung đột tài nguyên.
5. **Overlay display**: Cửa sổ OpenCV (`cv2.imshow`) hiển thị real-time:
   - Bounding box + label seatbelt (và phone, drinking, hands on/off...)
     từ YOLO.
   - Trạng thái drowsiness (fatigue_level, fatigue_score, EAR, PERCLOS...)
     dưới dạng text overlay.
   - Có thể pause/resume (phím 'p'), thoát (phím 'q').
6. **API endpoints giữ nguyên + mở rộng**: `/health` báo trạng thái cả 2
   model, `/stats` thống kê tổng hợp, `/frame` (debug).
7. **Graceful degradation**: Nếu không có video input, service khởi động
   bình thường (chờ input). Nếu không kết nối được RabbitMQ, vẫn chạy.

## 5. Ràng buộc
- **Không sửa logic AI gốc** của driver-service (MediaPipe pipeline,
  feature extraction, classifiers) và seatbelt_service (YOLO detector).
- **Video file local**: không webcam, không stream HTTP, không upload.
- **Python 3.11**, FastAPI, OpenCV, MediaPipe, Ultralytics YOLO.
- **Single-frame dual-inference**: 2 model chạy tuần tự trên 1 frame
  để tránh race condition trên GPU memory.

## 6. Service bị ảnh hưởng
- **driver-service** (`services/driver-service/`): ĐƯỢC SỬA ĐỔI —
  thêm seatbelt detector, video reader, overlay renderer; thay đổi
  orchestrator để hỗ trợ video file mode + dual-model pipeline.
- **seatbelt_service** (`services/seatbelt_service/`): KHÔNG bị sửa đổi —
  chỉ copy code/model sang driver-service.
- **services-map.md**: cập nhật trách nhiệm driver-service (thêm seatbelt
  detection, video file input mode).
