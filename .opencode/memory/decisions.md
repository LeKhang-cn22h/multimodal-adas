# Decision Log (ADR ngắn gọn)

> Append-only. Mỗi quyết định kiến trúc quan trọng thêm 1 entry mới ở CUỐI
> file, KHÔNG sửa/xoá entry cũ (nếu quyết định đổi, thêm entry mới ghi rõ
> "thay thế ADR-00X"). Agent PHẢI đọc file này trước khi đề xuất kiến trúc
> để không đề xuất lại thứ đã bị bác bỏ.

## ADR-001: Driver Service không tự mở webcam

- **Ngày**: (điền khi áp dụng thật)
- **Bối cảnh**: Ban đầu driver-service dùng `cv2.VideoCapture(0)` trực tiếp,
  xung đột với camera-service khi cả 2 cùng chạy.
- **Quyết định**: Driver Service lấy frame qua `GET /frame` của
  camera-service bằng `services/camera_client.py`. Camera-service là service
  DUY NHẤT được mở webcam.
- **Hệ quả**: Thêm 1 network hop mỗi lần lấy frame; đổi lại tránh xung đột
  tài nguyên phần cứng và giữ đúng ranh giới microservice.

## ADR-002: Artifact quy trình (REQ/FEAT/TS) lưu trong .opencode/knowledge/

- **Ngày**: (điền khi áp dụng thật)
- **Bối cảnh**: Cần chọn nơi lưu file sinh ra bởi /requirement, /feature,
  /techsolution.
- **Quyết định**: Lưu trong `.opencode/knowledge/requirements/`,
  `.opencode/knowledge/features/`, `.opencode/knowledge/tech-solutions/`
  thay vì 1 thư mục `docs/` riêng ở root.
- **Hệ quả**: Toàn bộ tri thức project (kiến trúc cố định + artifact theo
  từng task) nằm chung dưới `.opencode/knowledge/`, dễ nạp vào context qua
  `opencode.json -> instructions` nếu cần mở rộng sau này, nhưng cần lưu ý
  KHÔNG add cả thư mục requirements/features/tech-solutions vào
  `instructions` mặc định (sẽ phình context) — chỉ đọc theo yêu cầu (Read
  tool) khi command cần đúng 1 file cụ thể.

<!-- Thêm ADR mới bên dưới dòng này -->

## ADR-004: Giữ Face Landmarker 478, dùng facial_transformation_matrixes cho Head Pose

- **Ngày**: 2026-07-05
- **Bối cảnh**: REQ-drowsiness-detection ban đầu đề xuất chuyển sang MediaPipe
  Face Mesh (468 landmarks) và tự triển khai `solvePnP` để tính Head Pose
  (Yaw/Pitch/Roll). Tuy nhiên:
  - Code hiện tại đã dùng Face Landmarker (478 landmarks, `face_landmarker.task`)
    với EAR indices đã hardcode (mắt trái `[33, 160, 158, 133, 153, 144]`,
    mắt phải `[362, 385, 387, 263, 373, 380]`).
  - Face Landmarker output ĐÃ BAO GỒM `facial_transformation_matrixes`
    (ma trận 4x4) cho phép suy ra Head Pose trực tiếp, không cần viết
    `solvePnP` thủ công.
  - Chuyển sang Face Mesh sẽ làm thay đổi toàn bộ indices mắt/miệng, phải
    viết lại EAR/MAR từ đầu, không tận dụng được code đã test.
- **Quyết định**: Giữ nguyên MediaPipe Face Landmarker (478 landmarks) cho
  Landmark Layer. Head Pose trích xuất từ `facial_transformation_matrixes`
  thay vì tự triển khai `solvePnP`.
- **Lý do**: Tái sử dụng code EAR/MAR hiện có (không đổi indices), giảm rủi
  ro bug khi triển khai solvePnP thủ công, Face Landmarker là model mới hơn
  và được Google duy trì chính thức (Face Mesh là legacy).
- **Hệ quả**: `utils/ear.py` giữ nguyên không sửa. `utils/headpose.py` chỉ
  cần decompose rotation matrix từ transformation matrix → Euler angles,
  đơn giản hơn nhiều so với solvePnP đầy đủ.

<!-- Thêm ADR mới bên dưới dòng này -->

## ADR-005: Sliding window đếm theo số frame, không theo timestamp

- **Ngày**: 2026-07-08
- **Bối cảnh**: Cần chọn cơ chế cho sliding window của PERCLOS (900 frame),
  statistics (300 frame), và velocity (30 frame). Hai lựa chọn: (A) đếm theo
  số frame với giả định FPS=30 ổn định, (B) đếm theo thời gian thật dùng
  timestamp mỗi frame.
- **Quyết định**: Chọn **(A) đếm theo số frame**. Buffer là `deque[float]`
  với `max_size = window_seconds × FPS_ASSUMPTION`. Không lưu timestamp.
- **Lý do**: Đơn giản hơn nhiều — `deque` tự động pop khi đầy, O(1) mọi
  thao tác, dễ test, dễ debug. Timestamp-based đòi hỏi quản lý eviction
  theo thời gian, phức tạp hơn mà lợi ích không đáng kể khi FPS ổn định.
- **Hệ quả**:
  - `SlidingWindowBuffer.push(value: float)` chỉ nhận float, không nhận
    timestamp. Code đơn giản, không cần import `time`.
  - Rủi ro chấp nhận: nếu FPS thực tế < 30 (tải cao, network lag), cửa sổ
    900 frame đại diện cho > 30 giây thực → phản ứng chậm hơn. Chấp nhận
    được trong điều kiện vận hành bình thường.
  - Có thể override `FPS_ASSUMPTION` qua env var nếu cần.

<!-- Thêm ADR mới bên dưới dòng này -->

## ADR-006: Gộp camera-service vào driver-service thành 1 service duy nhất

- **Ngày**: 2026-07-11
- **Bối cảnh**: Kiến trúc microservice hiện tại tách camera-service
  (mở webcam, publish JPEG qua RabbitMQ) và driver-service (consume JPEG,
  chạy pipeline AI, publish kết quả). Việc tách 2 service tạo ra 1
  network hop qua RabbitMQ giữa 2 phần vốn luôn chạy cùng lúc và không
  có nhu cầu scale độc lập. Các service khác (lane, vehicle, seatbelt)
  hiện chỉ là ý tưởng trong tài liệu, chưa có kế hoạch triển khai thật.
- **Quyết định**: **Gộp camera-service và driver-service thành 1 service
  duy nhất**, giữ tên "driver-service". Driver-service đảm nhận CẢ việc
  mở webcam VÀ toàn bộ pipeline AI. Không còn camera-service độc lập.
- **Lý do**: Đơn giản hoá triển khai (1 container thay vì 2), giảm độ
  trễ (bỏ network hop qua RabbitMQ giữa capture và inference), các
  service tiềm năng khác chưa có kế hoạch thật nên không cần giữ khả
  năng chia sẻ frame qua message queue.
- **Hệ quả**:
  - **ADR-001 SUPERSEDED** (phần "camera-service là service riêng"):
    nguyên tắc "chỉ 1 nơi mở webcam" vẫn đúng, nhưng nơi đó giờ nằm
    trong driver-service thay vì 1 service riêng.
  - **ADR-003 SUPERSEDED một phần**: giao tiếp frame qua RabbitMQ giữa
    camera-service và driver-service không còn áp dụng (không còn 2
    service riêng biệt). Phần "publish kết quả driver.result qua
    RabbitMQ cho consumer bên ngoài" VẪN GIỮ NGUYÊN — hệ thống cảnh
    báo ADAS là consumer thật bên ngoài service.
  - Xoá bỏ `messaging/consumer.py` (FrameConsumer) và phần
    FramePublisher trong `messaging/publisher.py` — không còn ai
    publish/consume `driver.frame` nội bộ.
  - Giữ lại `ResultPublisher` (publish `driver.result`) cho consumer
    bên ngoài.
  - Driver-service giờ có 1 background thread mở webcam, gọi trực
    tiếp (function call) vào pipeline AI mỗi khi có frame mới.
  - Xoá thư mục `services/camera-service/` khỏi project.
  - Cập nhật `docker-compose.yml`: bỏ container camera-service,
    driver-service cần quyền truy cập webcam host (device mapping).