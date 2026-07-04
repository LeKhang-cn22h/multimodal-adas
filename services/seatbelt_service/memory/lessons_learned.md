# Bài học kinh nghiệm - Seatbelt-Service

## LL-001: Giữ nguyên AI code khi thay đổi communication layer

**Bài học**: Khi chuyển từ HTTP sang RabbitMQ, rủi ro lớn nhất là làm hỏng logic AI đã hoạt động. Bằng cách chỉ thay đổi lớp giao tiếp, giữ nguyên toàn bộ logic YOLO, quá trình chuyển đổi diễn ra suôn sẻ.

**Kết luận**: Tách biệt communication layer và AI layer ngay từ đầu. Không bao giờ sửa cả hai cùng lúc.

## LL-002: Backward compatibility quan trọng

**Bài học**: Giữ lại API `/check` và `/stats` cho phép API Gateway và monitoring tools tiếp tục hoạt động mà không cần thay đổi.

## LL-003: prefetch_count=1 tránh quá tải

**Bài học**: YOLO là tác vụ nặng. `prefetch_count=1` đảm bảo mỗi consumer chỉ xử lý 1 frame tại một thời điểm, tránh OOM.

## LL-004: Streak tracking giảm false alarm

**Bài học**: Yêu cầu N frame liên tiếp không có seatbelt mới kích hoạt warning giúp giảm đáng kể false alarm do YOLO bỏ sót 1-2 frame.
