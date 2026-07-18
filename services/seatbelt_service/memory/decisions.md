# Quyết định thiết kế - Seatbelt-Service

## DEC-001: Chuyển từ HTTP polling sang RabbitMQ consuming

**Ngày**: 2026-07-03

**Ngữ cảnh**: Seatbelt-Service trước đây gọi `httpx.get(camera/frame)` mỗi 3 giây để lấy frame. Cách này gây ra độ trễ không cần thiết và tạo áp lực lên Camera-Service.

**Quyết định**: Chuyển sang RabbitMQ consuming. Seatbelt-Service giờ đây thụ động nhận frame từ queue `seatbelt.frames`.

**Lý do**:
- Loại bỏ polling interval, giảm độ trễ.
- Không tạo HTTP request không cần thiết đến Camera-Service.
- Camera-Service chủ động kiểm soát tần suất gửi frame.

---

## DEC-002: Giữ nguyên toàn bộ code YOLO inference

**Ngày**: 2026-07-03

**Ngữ cảnh**: Cần quyết định có nên refactor lại code YOLO khi chuyển sang RabbitMQ không.

**Quyết định**: Giữ nguyên 100% code YOLO inference. Chỉ thay đổi cách nhận input (HTTP → RabbitMQ).

**Lý do**:
- Model YOLO đã được huấn luyện và kiểm chứng.
- Refactor AI code có rủi ro làm hỏng logic đã hoạt động.
- Tách biệt rõ ràng giữa communication layer và AI layer.

---

## DEC-003: Giữ lại API /check cho backward compatibility

**Ngày**: 2026-07-03

**Ngữ cảnh**: Khi chuyển sang RabbitMQ, kết quả được publish lên queue thay vì trả về qua HTTP. Nhưng một số thành phần (API Gateway, monitoring) vẫn cần HTTP endpoint.

**Quyết định**: Giữ lại endpoint `/check` nhưng thay đổi implementation. Thay vì fetch frame + chạy YOLO (như cũ), endpoint trả về trạng thái mới nhất từ bộ nhớ.

**Lý do**:
- Backward compatibility với API Gateway.
- Không phá vỡ hợp đồng API hiện có.
- Không tốn chi phí (chỉ đọc từ memory).

---

## DEC-004: prefetch_count=1 cho consumer

**Ngày**: 2026-07-03

**Ngữ cảnh**: Cần quyết định số lượng message consumer nhận cùng lúc.

**Quyết định**: Đặt `prefetch_count=1` - mỗi lần chỉ xử lý 1 frame.

**Lý do**:
- YOLO inference nặng, xử lý nhiều frame cùng lúc gây quá tải.
- Nếu chạy nhiều instance Seatbelt-Service, RabbitMQ tự động round-robin.
- Đảm bảo thứ tự xử lý frame.

---

## DEC-005: auto_ack=True cho frame consumer

**Ngày**: 2026-07-03

**Ngữ cảnh**: Cần quyết định cơ chế xác nhận message.

**Quyết định**: Dùng `auto_ack=True`.

**Lý do**:
- Nếu YOLO inference fail, frame đó không thể xử lý lại (đã quá cũ).
- Đơn giản hóa code.
- Kết quả seatbelt không critical - nếu mất 1-2 kết quả không ảnh hưởng lớn.

---

## DEC-006: Không vẽ bounding box lên ảnh

**Ngày**: 2026-07-03

**Ngữ cảnh**: `main_detection.py` (standalone script) có vẽ bounding box. Cần quyết định có nên tích hợp vào service API không.

**Quyết định**: Không vẽ bounding box trong service. Chỉ trả về JSON kết quả. Việc hiển thị để Camera-Service xử lý.

**Lý do**:
- Giảm kích thước message (không gửi ảnh đã vẽ).
- Tách trách nhiệm: Seatbelt phát hiện, Camera hiển thị.
- JSON nhẹ hơn ảnh JPEG rất nhiều.
