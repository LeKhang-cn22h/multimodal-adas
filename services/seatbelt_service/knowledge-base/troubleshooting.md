# Xử lý sự cố - Seatbelt-Service

## Model Not Found

**Triệu chứng**: `FileNotFoundError: YOLO model not found: best.pt`

**Giải pháp**:
- Copy file `best_1.pt` vào thư mục service.
- Hoặc đổi `MODEL_PATH=best_1.pt`.
- Trong Docker: đảm bảo file model được COPY vào image.

## RabbitMQ Connection Failed

Xem Camera-Service `knowledge-base/troubleshooting.md` (cùng nguyên nhân).

## YOLO Inference Chậm

**Triệu chứng**: `avg_inference_ms > 1000`

**Giải pháp**:
- Giảm `FRAME_WIDTH`/`FRAME_HEIGHT` ở Camera-Service.
- Tăng `SEATBELT_FRAME_INTERVAL` để giảm tần suất.
- Chạy nhiều instance Seatbelt-Service (round-robin).

## High Memory Usage

**Triệu chứng**: Container dùng >2GB RAM.

**Nguyên nhân**: YOLO model chiếm ~1-2GB.

**Giải pháp**: Tăng memory limit Docker. Hoặc dùng model nhẹ hơn.

## Warning Không Kích Hoạt

**Triệu chứng**: Tài xế không thắt seatbelt nhưng warning=False.

**Nguyên nhân**: `WARNING_FRAMES=10` - cần 10 frame liên tiếp không có seatbelt.

**Giải pháp**: Giảm `WARNING_FRAMES` nếu cần cảnh báo sớm hơn.
