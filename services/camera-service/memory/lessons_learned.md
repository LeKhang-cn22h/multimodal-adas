# Bài học kinh nghiệm - Camera-Service

Những kinh nghiệm rút ra trong quá trình phát triển và triển khai Camera-Service.

---

## LL-001: RabbitMQ giúp Camera không bị block bởi AI

**Bài học**: Khi chuyển từ HTTP đồng bộ sang RabbitMQ, FPS của camera tăng đáng kể vì không còn phải chờ AI xử lý xong.

**Trước**: Camera gửi frame qua HTTP → chờ response → tiếp tục capture. Nếu AI chậm, FPS giảm theo.

**Sau**: Camera publish frame → không chờ → tiếp tục capture. FPS độc lập hoàn toàn.

**Kết luận**: Message broker là lựa chọn đúng cho pipeline xử lý ảnh thời gian thực.

---

## LL-002: Không publish toàn bộ frame cho Seatbelt

**Bài học**: Ban đầu thiết kế publish mọi frame cho cả Driver và Seatbelt. Sau khi benchmark, nhận thấy Seatbelt (YOLO) không cần tần suất cao như Driver (MediaPipe EAR).

**Điều chỉnh**: Thêm `SEATBELT_FRAME_INTERVAL` (mặc định 600s) để throttle.

**Kết quả**: Giảm ~99% traffic RabbitMQ cho seatbelt mà không ảnh hưởng đến chất lượng phát hiện.

**Kết luận**: Không phải service AI nào cũng cần real-time. Phân tích nhu cầu thực tế trước khi thiết kế tần suất publish.

---

## LL-003: Thread riêng cho Display là cần thiết

**Bài học**: Ban đầu thử chạy `cv2.imshow` trong cùng capture thread. Kết quả: FPS hiển thị bằng FPS capture, nhưng khi cửa sổ bị resize hoặc di chuyển, capture bị giật.

**Điều chỉnh**: Tách display thành thread riêng với FPS cố định ~30.

**Kết quả**: Display mượt mà, không ảnh hưởng capture. Có thể pause display mà không dừng capture.

**Kết luận**: UI/Display luôn nên chạy trong thread riêng trong ứng dụng xử lý ảnh.

---

## LL-004: Exponential backoff là bắt buộc cho reconnect

**Bài học**: Khi thử nghiệm reconnect RabbitMQ với fixed delay 1s, service spam log và CPU cao. Khi RabbitMQ mất vài phút để restart, hàng trăm lần thử thất bại.

**Điều chỉnh**: Chuyển sang exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s (cap).

**Kết quả**: Log sạch hơn, CPU thấp hơn, vẫn reconnect nhanh khi RabbitMQ sẵn sàng.

**Kết luận**: Luôn dùng exponential backoff cho retry/reconnect logic.

---

## LL-005: Pydantic validation cho message parsing

**Bài học**: Khi consumer đầu tiên parse JSON thủ công (`json.loads` + dict access), một message sai format làm consumer crash.

**Điều chỉnh**: Dùng Pydantic model (`DriverResultMessage(**data)`) để validate. Thêm try-except để bắt `ValidationError`.

**Kết quả**: Message sai format bị log warning và bỏ qua, consumer tiếp tục chạy.

**Kết luận**: Luôn validate external data. Pydantic là công cụ tốt cho việc này.

---

## LL-006: Lock cho dữ liệu dùng chung giữa các thread

**Bài học**: Khi bỏ qua lock cho `latest_frame`, đôi khi display thread đọc frame đang được capture thread ghi dở → ảnh bị hỏng (nửa frame cũ, nửa frame mới).

**Điều chỉnh**: Tất cả read/write `latest_frame`, `latest_jpeg`, `frame_id`, `timestamp`, `fps` đều qua `threading.Lock`.

**Kết quả**: Không còn ảnh hỏng. Performance impact không đáng kể vì lock held rất ngắn.

**Kết luận**: Thread-safety là yêu cầu bắt buộc trong multi-threaded application.

---

## LL-007: Docker không phù hợp cho webcam trên Windows

**Bài học**: Dành nhiều thời gian cấu hình Docker để truy cập webcam trên Windows, nhưng không thành công do hạn chế của Docker Desktop.

**Điều chỉnh**: Chấp nhận chạy Camera-Service natively trên Windows. Các service khác vẫn trong Docker.

**Kết luận**: Không phải service nào cũng nên Docker hóa. Các service cần truy cập phần cứng (webcam, GPU) nên cân nhắc chạy native.

---

## LL-008: Log có cấu trúc giúp debug nhanh hơn

**Bài học**: Với 4 thread chạy đồng thời, log không có cấu trúc rất khó debug. Cần biết log từ thread nào, service nào.

**Điều chỉnh**: Dùng format: `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s` với `%(name)s` là `camera-service`.

**Kết quả**: Có thể filter log theo service, dễ dàng trace qua các thread.

**Kết luận**: Đầu tư vào logging từ đầu. Structured logging tiết kiệm hàng giờ debug.
