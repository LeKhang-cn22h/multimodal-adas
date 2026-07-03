# Quyết định thiết kế - Camera-Service

Tài liệu này ghi lại các quyết định thiết kế quan trọng trong quá trình phát triển Camera-Service. Mỗi quyết định bao gồm ngữ cảnh, lựa chọn và lý do.

---

## DEC-001: Chuyển từ HTTP đồng bộ sang RabbitMQ bất đồng bộ

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Trước đây, Camera-Service sử dụng HTTP để phục vụ frame cho Seatbelt-Service (qua endpoint `/frame`) và nhận kết quả qua HTTP (qua `/check`). Điều này gây ra vấn đề:
- Camera FPS bị giảm khi AI chậm (do polling HTTP).
- Không thể mở rộng - mỗi service gọi HTTP riêng.
- Không có buffer khi service đích chết.

**Lựa chọn**:
1. Giữ nguyên HTTP.
2. Chuyển sang RabbitMQ.
3. Chuyển sang Kafka.

**Quyết định**: Chọn RabbitMQ vì:
- Nhẹ hơn Kafka, phù hợp với quy mô hiện tại.
- Hỗ trợ topic exchange - linh hoạt routing.
- Tích hợp tốt với Python qua thư viện pika.
- Có sẵn Docker image chính thức.
- Management UI giúp debug dễ dàng.

---

## DEC-002: Camera chỉ publish frame, không xử lý AI

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Cần quyết định nơi thực hiện suy luận AI: tại Camera-Service hay tại các service riêng biệt.

**Lựa chọn**:
1. Camera-Service vừa capture vừa chạy AI.
2. Camera-Service chỉ capture, AI chạy ở service riêng.

**Quyết định**: Chọn phương án 2 - Camera-Service **không bao giờ** thực hiện suy luận AI. Lý do:
- Tách biệt trách nhiệm (Single Responsibility).
- Camera FPS không phụ thuộc vào tốc độ AI.
- Có thể scale AI service độc lập (thêm nhiều consumer).
- Dễ bảo trì - thay đổi AI không ảnh hưởng đến capture.

---

## DEC-003: Overlay kết quả AI thực hiện tại Camera-Service

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Cần hiển thị kết quả AI lên màn hình giám sát. Có thể thực hiện overlay ở nhiều nơi.

**Lựa chọn**:
1. Overlay tại Camera-Service (nhận kết quả qua RabbitMQ).
2. Overlay tại một service riêng (desktop monitor).
3. Mỗi AI service tự hiển thị.

**Quyết định**: Chọn phương án 1 - overlay tại Camera-Service. Lý do:
- Camera-Service đã có sẵn cv2.imshow.
- Kết quả AI được consume trực tiếp từ RabbitMQ (không cần HTTP polling).
- Một cửa sổ duy nhất hiển thị tất cả thông tin.
- Không cần thêm service monitor riêng.

---

## DEC-004: Sử dụng raw JPEG bytes trong message body, metadata trong headers

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Cần quyết định định dạng message cho frame: JSON + Base64 hay raw binary + headers.

**Lựa chọn**:
1. JSON body với JPEG base64-encoded.
2. Raw JPEG body + AMQP headers cho metadata.

**Quyết định**: Chọn phương án 2 - raw JPEG + headers. Lý do:
- Base64 tăng kích thước ~33%.
- JPEG đã là binary format, không cần wrapper.
- Headers được RabbitMQ index, có thể dùng để routing/filtering.
- Consumer chỉ cần đọc body bytes, không cần parse JSON.

---

## DEC-005: Seatbelt frame gửi theo interval (mặc định 10 phút)

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Driver-Service cần MỌI frame để sliding window hoạt động, nhưng Seatbelt-Service (YOLO) không cần tần suất cao như vậy.

**Lựa chọn**:
1. Gửi mọi frame cho cả hai service.
2. Gửi mọi frame cho Driver, interval cho Seatbelt.

**Quyết định**: Chọn phương án 2 - Throttle seatbelt frames. Lý do:
- YOLO inference nặng, không cần chạy mỗi frame.
- Dây an toàn là trạng thái ít thay đổi (người đã thắt thì giữ nguyên).
- Giảm tải cho Seatbelt-Service và RabbitMQ.
- Có thể cấu hình interval qua biến môi trường.

---

## DEC-006: Sử dụng pika thay vì aio-pika

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Cần chọn thư viện RabbitMQ client cho Python.

**Lựa chọn**:
1. `pika` (đồng bộ, BlockingConnection).
2. `aio-pika` (bất đồng bộ, asyncio).

**Quyết định**: Chọn `pika`. Lý do:
- Đơn giản hơn, dễ debug.
- Mỗi consumer/publisher chạy trong thread riêng (threading, không cần asyncio).
- FastAPI xử lý HTTP qua asyncio, nhưng messaging dùng thread riêng - không conflict.
- pika ổn định hơn, cộng đồng lớn hơn.

---

## DEC-007: Auto-ack cho result consumer

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Cần quyết định cơ chế xác nhận message cho result consumer.

**Lựa chọn**:
1. auto_ack=True (tự động ack ngay khi nhận).
2. auto_ack=False (ack thủ công sau khi xử lý).

**Quyết định**: Chọn `auto_ack=True` cho result consumer. Lý do:
- Kết quả AI không critical - nếu mất một vài kết quả, overlay chỉ hiển thị kết quả cũ.
- Không cần xử lý phức tạp như dead-letter.
- Đơn giản hóa code consumer.
- Tránh tắc nghẽn nếu consumer không kịp ack.

---

## DEC-008: Frame publisher dùng delivery_mode=2 (persistent)

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Cần quyết định độ bền của frame message.

**Lựa chọn**:
1. delivery_mode=1 (non-persistent - mất khi RabbitMQ restart).
2. delivery_mode=2 (persistent - tồn tại sau restart).

**Quyết định**: Chọn `delivery_mode=2`. Lý do:
- Frame từ camera là dữ liệu quan trọng, không nên mất khi RabbitMQ restart.
- Chi phí disk I/O chấp nhận được.
- Driver-Service dùng sliding window - mất frame có thể ảnh hưởng đến kết quả.

---

## DEC-009: Tách biệt display thread khỏi capture thread

**Ngày**: 2026-07-03

**Ngữ cảnh**:
Cần quyết định nơi chạy cv2.imshow.

**Lựa chọn**:
1. Hiển thị trong cùng capture thread.
2. Hiển thị trong thread riêng.

**Quyết định**: Chọn phương án 2 - display thread riêng. Lý do:
- Display FPS (~30) khác với capture FPS (tối đa phần cứng).
- Nếu display chậm (vd: resize window), không ảnh hưởng capture.
- Có thể tạm dừng display mà không dừng capture.
- Clean architecture - mỗi thread một trách nhiệm.
