# FEAT-merged-monitoring: Feature Breakdown — Gộp Seatbelt + Video Input vào Driver-Service

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-merged-monitoring.md`

---

## Feature 1: FEAT-seatbelt-to-driver — Tích hợp Seatbelt Detector vào Driver-Service

### Service
`driver-service` (`services/driver-service/`)

### Mô tả chức năng
Copy toàn bộ logic YOLO seatbelt detection từ `seatbelt_service` vào
`driver-service`. Cụ thể:
- Copy model file `best_1.pt` vào `driver-service/`.
- Tạo file `app/services/seatbelt_detector.py` (copy từ seatbelt_service
  `app/services/seatbelt_detector.py`, giữ nguyên class `SeatbeltDetector`).
- Thêm dependency `ultralytics` vào `requirements.txt` của driver-service.
- Model được load 1 lần khi app khởi động (trong lifespan).
- **Không sửa code gốc** của `seatbelt_service`.

### Acceptance Criteria
1. `SeatbeltDetector.load_model()` load thành công `best_1.pt`, in ra 7 class names.
2. `SeatbeltDetector.process(jpeg_bytes, frame_id, timestamp)` trả về dict
   `{frame_id, timestamp, seatbelt: bool, confidence: float}`.
3. `SeatbeltDetector.is_loaded == True` sau khi load model.
4. Model chỉ load 1 lần, không reload mỗi request.
5. Code gốc của `seatbelt_service` không bị sửa đổi.

### Độ ưu tiên
**P0** — là feature nền tảng, các feature khác phụ thuộc vào.

### Phụ thuộc
Không — feature độc lập, chỉ cần `best_1.pt` và `ultralytics`.

---

## Feature 2: FEAT-video-frame-source — Video File thay thế Webcam làm nguồn frame

### Service
`driver-service` (`services/driver-service/`)

### Mô tả chức năng
Thêm chế độ đọc video file local làm nguồn frame, thay thế webcam
(`CameraCaptureService`) khi người dùng cung cấp đường dẫn video.
- Tạo file `app/services/video_file_reader.py` với class `VideoFileReader`:
  - Mở video bằng `cv2.VideoCapture(video_path)`.
  - Chạy trong background thread (giống `CameraCaptureService`).
  - Đọc từng frame, encode JPEG, push vào `queue.Queue` cho worker thread.
  - Hỗ trợ pause/resume, tự động loop hoặc dừng khi hết video.
- `CameraCaptureService` **giữ nguyên**, không sửa — service hỗ trợ cả 2
  chế độ: webcam (mặc định) hoặc video file (khi set env var `VIDEO_PATH`).
- Khi dùng video file, FPS được lấy từ metadata video, không cần tính.

### Acceptance Criteria
1. Set `VIDEO_PATH=/path/to/video.mp4` → service đọc frame từ video,
   không mở webcam.
2. Không set `VIDEO_PATH` → service dùng webcam như cũ (không break).
3. Đọc đúng độ phân giải, FPS từ metadata video.
4. Khi video hết: dừng hoặc loop (cấu hình qua env var `VIDEO_LOOP=true/false`).
5. Pause/resume hoạt động qua API endpoint mới (VD: `POST /video/pause`,
   `POST /video/resume`).

### Độ ưu tiên
**P0** — input source là điều kiện tiên quyết để chạy pipeline.

### Phụ thuộc
Không — chỉ phụ thuộc OpenCV (`cv2.VideoCapture`).

---

## Feature 3: FEAT-dual-inference-orchestrator — Orchestrator chạy đồng thời 2 Model

### Service
`driver-service` (`services/driver-service/`)

### Mô tả chức năng
Sửa `app/messaging/orchestrator.py` để worker thread xử lý mỗi frame qua
CẢ 2 pipeline AI (drowsiness + seatbelt) thay vì chỉ drowsiness.
- Inject `SeatbeltDetector` vào orchestrator (constructor hoặc factory).
- Worker thread: mỗi khi nhận JPEG từ queue:
  1. Decode JPEG → BGR numpy array.
  2. Gọi `FatigueDetector.process()` → drowsiness result.
  3. Gọi `SeatbeltDetector.process()` → seatbelt result.
  4. Merge 2 kết quả vào 1 dict tổng hợp.
  5. Publish qua RabbitMQ (nếu có).
  6. Đẩy frame + kết quả vào queue hiển thị (cho overlay — Feature 4).
- **Không sửa logic AI** của FatigueDetector và SeatbeltDetector.

### Acceptance Criteria
1. Mỗi frame tạo ra 1 dict kết quả chứa cả `fatigue_*` và `seatbelt_*`.
2. 2 model chạy tuần tự, không block lẫn nhau.
3. Nếu MediaPipe không detect được face → seatbelt vẫn chạy bình thường.
4. Nếu YOLO không detect được seatbelt → drowsiness vẫn chạy bình thường.
5. Inference time được track riêng cho từng model.

### Độ ưu tiên
**P0** — đây là logic tích hợp chính.

### Phụ thuộc
- FEAT-seatbelt-to-driver (cần `SeatbeltDetector`).
- FEAT-video-frame-source (cần frame từ video file để test).

---

## Feature 4: FEAT-overlay-render — Hiển thị Overlay Detection lên Frame

### Service
`driver-service` (`services/driver-service/`)

### Mô tả chức năng
Vẽ kết quả detection của cả 2 model lên frame và hiển thị qua cửa sổ OpenCV.
- Tạo file `app/services/overlay_renderer.py` với class `OverlayRenderer`:
  - Nhận BGR frame + kết quả drowsiness + kết quả seatbelt.
  - **Seatbelt overlay**: bounding box + label + confidence cho tất cả
    class YOLO detect được (cell phone, drinking, eyeglass, hands on/off,
    mask, seatbelt). Dùng màu riêng cho từng class.
  - **Drowsiness overlay**: text hiển thị fatigue_level, fatigue_score,
    EAR, PERCLOS, MAR ở góc frame.
  - **Status bar**: thanh trạng thái trên cùng — SEATBELT OK/WARNING +
    FATIGUE Awake/Tired/Drowsy/Dangerous.
  - Trả về frame đã vẽ overlay.
- Chạy trong 1 thread riêng (display thread) để không block inference:
  - Nhận frame đã render từ queue hiển thị.
  - Gọi `cv2.imshow()`.
  - Xử lý phím: 'q' = quit, 'p' = pause/resume.
- Có thể bật/tắt display qua env var `ENABLE_DISPLAY=true/false`.

### Acceptance Criteria
1. Bounding box YOLO vẽ đúng vị trí, có label + confidence.
2. Text drowsiness hiển thị rõ ràng, không che khuất nội dung chính.
3. Status bar cập nhật real-time theo kết quả detection.
4. Phím 'q' thoát, 'p' pause/resume hoạt động.
5. Khi `ENABLE_DISPLAY=false`, không mở cửa sổ OpenCV (headless mode).
6. Màu sắc phân biệt rõ các class YOLO và mức độ fatigue.

### Độ ưu tiên
**P1** — quan trọng cho demo, nhưng không block inference pipeline.

### Phụ thuộc
- FEAT-dual-inference-orchestrator (cần kết quả từ cả 2 pipeline).
