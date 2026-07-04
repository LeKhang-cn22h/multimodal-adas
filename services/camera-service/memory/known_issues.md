# Lỗi và hạn chế đã biết - Camera-Service

Tài liệu này liệt kê các lỗi, hạn chế và vấn đề đã biết trong phiên bản hiện tại của Camera-Service.

---

## KN-001: Delay nhẹ trên overlay

**Mức độ**: Thấp

**Mô tả**: Kết quả AI hiển thị trên overlay có thể bị delay 1-2 giây so với thời điểm thực do thời gian xử lý của AI service và độ trễ RabbitMQ.

**Nguyên nhân**: 
- Driver-Service cần thời gian xử lý MediaPipe + sliding window.
- Seatbelt-Service cần thời gian chạy YOLO inference.
- RabbitMQ thêm độ trễ ~10-50ms mỗi message.

**Workaround**: Không có. Đây là độ trễ tự nhiên của pipeline bất đồng bộ.

**Kế hoạch sửa**: Có thể thêm timestamp gốc vào kết quả để hiển thị tuổi của kết quả.

---

## KN-002: Seatbelt chỉ kiểm tra theo interval

**Mức độ**: Thấp (by design)

**Mô tả**: Seatbelt-Service chỉ nhận frame mỗi `SEATBELT_FRAME_INTERVAL` giây (mặc định 600s). Trong khoảng thời gian giữa các lần kiểm tra, overlay hiển thị kết quả cũ.

**Nguyên nhân**: Đây là quyết định thiết kế (DEC-005) để giảm tải cho Seatbelt-Service.

**Workaround**: Giảm `SEATBELT_FRAME_INTERVAL` nếu cần tần suất cao hơn.

**Kế hoạch sửa**: Có thể thêm cơ chế trigger kiểm tra seatbelt khi có sự kiện (ví dụ: phát hiện tài xế thay đổi).

---

## KN-003: Không hỗ trợ nhiều camera

**Mức độ**: Trung bình

**Mô tả**: Hiện tại chỉ hỗ trợ 1 webcam (camera index đơn). Không thể thu nhận từ nhiều nguồn camera cùng lúc.

**Nguyên nhân**: `CameraManager` được thiết kế cho một `cv2.VideoCapture`.

**Workaround**: Chạy nhiều instance Camera-Service trên các port khác nhau với `CAMERA_INDEX` khác nhau.

**Kế hoạch sửa**: Refactor `CameraManager` thành `MultiCameraManager` trong phiên bản tương lai.

---

## KN-004: Frame message không có TTL

**Mức độ**: Trung bình

**Mô tả**: Frame messages trong queue không tự động expire. Nếu consumer offline lâu, frame cũ vẫn tồn tại trong queue và sẽ được xử lý khi consumer online trở lại.

**Nguyên nhân**: Queue không được cấu hình `x-message-ttl`.

**Workaround**: Xóa queue thủ công qua RabbitMQ Management UI khi cần.

**Kế hoạch sửa**: Thêm TTL cho frame messages (vd: 5 giây) để tự động bỏ frame cũ.

---

## KN-005: OpenCV window không hoạt động trong Docker

**Mức độ**: Trung bình

**Mô tả**: `cv2.imshow` yêu cầu display server. Trong Docker container, không có X11 server nên không thể hiển thị cửa sổ.

**Nguyên nhân**: Docker không có quyền truy cập display server của host.

**Workaround**: 
1. Chạy Camera-Service natively trên host (không trong Docker).
2. Hoặc mount X11 socket: `-v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$DISPLAY`.

**Kế hoạch sửa**: Thêm option chạy headless mode (không hiển thị, chỉ publish frame).

---

## KN-006: Không có cơ chế health check cho webcam

**Mức độ**: Thấp

**Mô tả**: Khi webcam bị ngắt, `CameraManager` tự động thử reconnect, nhưng endpoint `/health` vẫn báo `healthy` nếu capture thread vẫn chạy.

**Nguyên nhân**: `is_running` chỉ kiểm tra thread còn sống, không kiểm tra camera có mở không.

**Workaround**: Gọi `/info` để kiểm tra `frame_id` có tăng không. Nếu `frame_id` đứng yên → camera bị lỗi.

**Kế hoạch sửa**: Thêm `camera_connected` flag vào `HealthResponse`.

---

## KN-007: Memory leak khi xử lý nhiều frame

**Mức độ**: Thấp

**Mô tả**: `latest_frame` lưu bản sao numpy array của frame gốc. Nếu display thread không kịp đọc, bản sao cũ vẫn tồn tại trong bộ nhớ đến khi GC chạy.

**Nguyên nhân**: `latest_frame.copy()` tạo bản sao mới mỗi lần gọi.

**Workaround**: Không cần. Python GC sẽ xử lý.

**Kế hoạch sửa**: Có thể dùng circular buffer thay vì copy.

---

## KN-008: Không hỗ trợ reconnect khi RabbitMQ đổi IP

**Mức độ**: Thấp

**Mô tả**: Nếu RabbitMQ container restart và nhận IP mới, Camera-Service có thể không reconnect được nếu dùng hostname không được DNS cập nhật.

**Nguyên nhân**: Docker DNS có thể cache IP cũ.

**Workaround**: Restart Camera-Service container.

**Kế hoạch sửa**: Thêm cơ chế force reconnect sau N lần thất bại liên tiếp.
