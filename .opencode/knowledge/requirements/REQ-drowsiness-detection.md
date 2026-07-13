# REQ-drowsiness-detection: Driver Drowsiness Detection Module

## 1. Actor

- **Tài xế**: đối tượng được giám sát (khuôn mặt là input gián tiếp qua camera cabin)
- **Hệ thống cảnh báo ADAS**: consumer của kết quả fatigue, nhận qua RabbitMQ routing `driver.result` để kích hoạt cảnh báo (âm thanh, rung vô-lăng, HUD...)
- **Dashboard/frontend** (tương lai): hiển thị trạng thái fatigue theo thời gian thực
- **Camera-service**: producer của frame JPEG, publish lên `adas.exchange` routing `driver.frame`

## 2. Mục tiêu

Xây dựng module phát hiện buồn ngủ tài xế hoàn chỉnh, thay thế pipeline EAR đơn giản hiện tại bằng pipeline 3 tầng:

1. **Landmark Layer**: Trích xuất facial landmarks từ mỗi frame
2. **Feature Extraction Layer**: Tính toán các đặc trưng sinh lý (EAR, PERCLOS, MAR, Head Pose)
3. **Classification Layer**: Phân loại mức độ buồn ngủ bằng Random Forest

Mục tiêu nghiệp vụ: phát hiện sớm và chính xác trạng thái buồn ngủ/thiếu tập trung của tài xế, giảm thiểu tai nạn do ngủ gật.

## 3. Ngữ cảnh

### Hiện trạng code (theo sync-context ngày 2026-07-05)

- **driver-service** đã có pipeline RabbitMQ hoạt động:
  - `messaging/consumer.py` (FrameConsumer): consume JPEG từ queue `driver.frames`
  - `services/fatigue_detector.py` (FatigueDetector): MediaPipe Face Landmarker (478 landmarks) + EAR sliding window → sleepy bool
  - `messaging/publisher.py` (ResultPublisher): publish kết quả lên `driver.result`
- **Đã có**: `utils/ear.py` (pure function `calculate_ear()`), `core/config.py` (threshold)
- **Stub rỗng chờ implement**: `utils/mar.py`, `utils/headpose.py`, `services/feature_service.py`, `services/mediapipe_service.py`, `services/fatigue_service.py`
- **Model hiện tại**: `face_landmarker.task` (MediaPipe Face Landmarker, 478 landmarks)
- **Dataset chưa có**: NTHU-DDD và YawDD cần được thu thập/tải về
- **requirements.txt** đã có sẵn: `scikit-learn`, `pandas`, `joblib` (chưa dùng)

### Kiến trúc đã chốt

- **ADR-001** (sẽ bị thay thế bởi ADR-003): driver-service từng lấy frame qua HTTP, nay đã chuyển sang RabbitMQ
- **ADR-003** (cần formalize): giao tiếp frame/result giữa camera-service và driver-service qua RabbitMQ (`adas.exchange`, routing `driver.frame` / `driver.result`), không cần REST endpoint `/fatigue`
- Camera-service vẫn là service DUY NHẤT mở webcam, publish JPEG lên RabbitMQ

### Lưu ý về ADR-003

> ⚠️ **ADR-003 chưa tồn tại trong `decisions.md`**. Yêu cầu này tham chiếu ADR-003 như đã chốt, nhưng thực tế ADR-003 mới chỉ được đề xuất trong báo cáo sync-context. Cần chính thức thêm ADR-003 vào `decisions.md` trước hoặc trong bước Tech Solution.

## 4. Acceptance Criteria

### AC-1: Landmark Layer
- [ ] **AC-1.1**: Module nhận JPEG bytes (từ RabbitMQ consumer), decode thành numpy array BGR, chuyển sang RGB, đưa vào MediaPipe Face Landmarker (model `face_landmarker.task` đã có sẵn)
- [ ] **AC-1.2**: MediaPipe Face Landmarker trả về **478 facial landmarks** (mỗi landmark có x, y, z tọa độ chuẩn hóa) + `facial_transformation_matrixes` cho đúng 1 khuôn mặt (`num_faces=1`). Tái sử dụng code Face Landmarker hiện có trong `fatigue_detector.py`, không đổi sang Face Mesh legacy.
- [ ] **AC-1.3**: Nếu không phát hiện khuôn mặt → trả về `None` landmarks, Classification Layer output mặc định là `"Unknown"` (không crash)

### AC-2: Feature Extraction Layer
- [ ] **AC-2.1**: EAR (Eye Aspect Ratio) — tính cho cả mắt trái và mắt phải, trả về giá trị trung bình. Dùng bộ landmark indices của **Face Landmarker** (478 điểm) — indices mắt trái `[33, 160, 158, 133, 153, 144]`, mắt phải `[362, 385, 387, 263, 373, 380]` — tái sử dụng trực tiếp `utils/ear.py` hiện có, không cần thay đổi
- [ ] **AC-2.2**: PERCLOS (Percentage of Eye Closure) — tỉ lệ % thời gian mắt đóng trong sliding window N giây (configurable, default 30s). Mắt được coi là "đóng" khi EAR < threshold
- [ ] **AC-2.3**: MAR (Mouth Aspect Ratio) — phát hiện ngáp dựa trên tỉ lệ mở miệng, dùng đúng Face Landmarker mouth indices. Định nghĩa indices ngoài (môi trên/dưới) và trong (khoang miệng) dựa trên Face Landmarker 478-point topology
- [ ] **AC-2.4**: Head Pose Estimation — tính Yaw, Pitch, Roll (độ) bằng cách trích xuất từ `facial_transformation_matrixes` có sẵn trong output của Face Landmarker (ma trận 4x4). KHÔNG tự triển khai `solvePnP` thủ công. Công thức: decompose rotation matrix từ transformation matrix → extract Euler angles (Yaw/Pitch/Roll)
- [ ] **AC-2.5**: Tất cả feature functions trong `utils/` là pure function (không I/O, không network, không state), nhận landmarks array, trả về float

### AC-3: Classification Layer
- [ ] **AC-3.1**: Input vector 40 chiều (xem danh sách đầy đủ trong `TS-feature-extraction.md` § "FeatureVector 40 fields"): 7 root features (EAR_left, EAR_right, EAR_avg, MAR, Yaw, Pitch, Roll) + 28 statistical features (mean/std/min/max qua N=300 backward window) + 5 temporal/behavioral features (PERCLOS, blink_rate qua N=900; yaw/pitch/roll_velocity qua N=30)
- [ ] **AC-3.2**: Output là **Fatigue Score** (int, 0-100) — 0 = hoàn toàn tỉnh táo, 100 = nguy hiểm (ngủ gật). Mapping: 0-25 → Awake, 26-50 → Tired, 51-75 → Drowsy, 76-100 → Dangerous
- [ ] **AC-3.3**: Pipeline huấn luyện BAO GỒM: (a) tải dataset NTHU-DDD từ nguồn công khai, (b) tiền xử lý: chạy Face Landmarker trên toàn bộ ảnh để trích xuất feature vector 40 chiều kèm label, (c) train Random Forest + XGBoost baseline với LOSO-CV 4-fold (không yêu cầu accuracy production, chỉ cần chạy demo được). Model lưu dưới dạng `.pkl`, load 1 lần khi app khởi động (trong `lifespan`). Script huấn luyện là standalone (không nằm trong app runtime), đặt trong `driver-service/training/`
- [ ] **AC-3.4**: Dataset huấn luyện: **NTHU-DDD** (National Tsing Hua University Driver Drowsiness Detection) + **YawDD** (Yawning Detection Dataset). Dataset hiện **CHƯA CÓ SẴN** — bước tải + preprocess nằm trong phạm vi công việc. Cần script tự động hóa: tải từ URL công khai, giải nén, extract features bằng Face Landmarker, gán label, lưu thành `.csv` để train
- [ ] **AC-3.5**: Fallback rule-based (dùng khi model `.pkl` không tồn tại hoặc lỗi load). Công thức PERCLOS-based 4 cấp:
  - **Awake**: PERCLOS < 15% **và** không ngáp kéo dài (MAR < threshold trong ≥ 90% sliding window)
  - **Tired**: PERCLOS 15–25%, **hoặc** ngáp lặp lại (MAR > threshold ≥ 3 lần trong 60 giây)
  - **Drowsy**: PERCLOS 25–40%, **hoặc** cúi/nghiêng đầu bất thường kéo dài (|Pitch| > 20° hoặc |Yaw| > 25° liên tục ≥ 3 giây)
  - **Dangerous**: PERCLOS > 40%, **hoặc** nhắm mắt liên tục vượt ngưỡng microsleep (EAR < threshold liên tục ≥ 2 giây)
  - Fatigue Score nội suy tuyến tính từ PERCLOS: `score = min(100, PERCLOS * 2.5)` (PERCLOS 40% → score 100)
  - Mọi threshold (EAR, MAR, PERCLOS %, Pitch/Yaw góc, thời gian) lưu trong `core/config.py`

### AC-4: Output qua RabbitMQ
- [ ] **AC-4.1**: Kết quả publish lên `adas.exchange` với routing key `driver.result`, body là JSON gồm: `frame_id`, `timestamp`, `fatigue_score` (0-100), `fatigue_level` ("Awake"|"Tired"|"Drowsy"|"Dangerous"), `features` (object: `{ear, perclos, mar, yaw, pitch, roll}`), `confidence` (0-1)
- [ ] **AC-4.2**: Không cần REST endpoint `/fatigue` — toàn bộ output qua RabbitMQ
- [ ] **AC-4.3**: Giữ nguyên các endpoint hiện có `/health` và `/stats` (cập nhật stats cho khớp pipeline mới)

### AC-5: Hiệu năng
- [ ] **AC-5.1**: Pipeline hoàn chỉnh (JPEG decode → landmarks → features → classify → publish) có latency trung bình ≤ 100ms/frame trên CPU (không GPU)
- [ ] **AC-5.2**: Không drop frame quá 5% ở chế độ 30 FPS đầu vào
- [ ] **AC-5.3**: Model Random Forest file size ≤ 10MB

## 5. Ràng buộc

| Ràng buộc | Chi tiết |
|---|---|
| **Frame nguồn** | JPEG bytes từ RabbitMQ queue `driver.frames` (không tự mở webcam, không gọi HTTP) |
| **Landmark model** | MediaPipe Face Landmarker (478 landmarks), model `face_landmarker.task` đã có sẵn. Head Pose trích xuất từ `facial_transformation_matrixes`, không tự viết `solvePnP` |
| **Ngôn ngữ** | Python 3.11+, type hint đầy đủ |
| **Pure function** | Tất cả feature extraction (EAR, MAR, HeadPose) trong `utils/`, không I/O |
| **Model load** | Random Forest load 1 lần trong lifespan, không load lại mỗi request/frame |
| **Threshold** | Mọi threshold (EAR, MAR, PERCLOS window...) lưu trong `core/config.py` |
| **Dataset** | NTHU-DDD + YawDD: chưa có sẵn. Phạm vi công việc BAO GỒM tải + tiền xử lý + train baseline Random Forest. Script huấn luyện trong `driver-service/training/` |
| **Không REST** | Không thêm endpoint `/fatigue`, output chỉ qua RabbitMQ |

## 6. Service bị ảnh hưởng

| Service | Ảnh hưởng |
|---|---|
| **driver-service** | 🎯 **Chính**: toàn bộ module nằm trong service này. Sẽ tạo/sửa: `utils/ear.py` (giữ nguyên, không đổi indices), `utils/mar.py` (mới), `utils/headpose.py` (mới — decompose transformation matrix), `services/feature_service.py` (mới), `services/fatigue_detector.py` (refactor lớn — tích hợp pipeline 3 tầng), `services/mediapipe_service.py` (mới — Face Landmarker wrapper tách riêng), `models/` (thêm message schema mới), `core/config.py` (thêm threshold MAR, PERCLOS, HeadPose, microsleep), `messaging/consumer.py` (cập nhật output format). Thêm thư mục `training/` chứa script tải dataset + preprocess + train |
| **camera-service** | Không thay đổi — vẫn publish JPEG lên `driver.frame` như hiện tại. Tuy nhiên `models/messages.py` (DriverResultMessage) có thể cần cập nhật để khớp schema mới |
| **seatbelt-service** | Không ảnh hưởng |
| **lane-service** | Không ảnh hưởng |
| **frontend** | Ảnh hưởng gián tiếp: nếu frontend đang subscribe RabbitMQ `driver.result`, cần cập nhật parser cho schema mới |

---

## 7. Quyết định đã chốt (từ câu hỏi mở ban đầu)

1. **Landmark model**: Giữ nguyên MediaPipe Face Landmarker (478 điểm, `face_landmarker.task`), không chuyển sang Face Mesh 468. Xem ADR-004.
2. **Head Pose**: Tận dụng `facial_transformation_matrixes` từ Face Landmarker output thay vì tự viết `solvePnP`. Xem ADR-004.
3. **Dataset**: NTHU-DDD + YawDD chưa có sẵn — phạm vi công việc bao gồm tải + preprocess + train baseline.
4. **Rule-based fallback**: Dùng công thức PERCLOS-based 4 cấp cụ thể (xem AC-3.5).
5. **Output format**: Fatigue Score (0-100) là output chính, level string ("Awake"/"Tired"/"Drowsy"/"Dangerous") được derived từ score.
