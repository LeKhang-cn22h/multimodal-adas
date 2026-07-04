# Thuật ngữ - Seatbelt-Service

## Các thuật ngữ đặc thù

### YOLO (You Only Look Once)
Mô hình object detection thời gian thực. Seatbelt-Service dùng YOLO từ Ultralytics.

### Class ID
Mã số định danh cho mỗi lớp đối tượng. `SEATBELT_CLASS_ID = 6`.

### Confidence Threshold
Ngưỡng độ tin cậy tối thiểu để chấp nhận một detection. Mặc định 0.3.

### Streak
Số frame liên tiếp không phát hiện seatbelt. Dùng để tránh false alarm.

### WARNING_FRAMES
Ngưỡng streak để kích hoạt warning. Mặc định 10 frame.

### Prefetch Count
Số message consumer nhận trước cùng lúc. Seatbelt-Service dùng `prefetch_count=1`.

### best_1.pt
File model YOLO trained. Chứa weights cho 7 classes.

Các thuật ngữ chung về RabbitMQ, Docker, FastAPI: xem Camera-Service `knowledge-base/glossary.md`.
