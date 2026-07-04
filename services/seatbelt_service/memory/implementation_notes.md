# Ghi chú triển khai - Seatbelt-Service

## Quy tắc quan trọng

### 1. KHÔNG sửa code YOLO inference

Các phương thức sau **không được thay đổi**:
- `_run_inference()` - logic YOLO chính.
- `_decode_jpeg()` - giải mã ảnh.
- `_update_stats()` - cập nhật streak.
- `load_model()` - tải model.
- `CLASS_NAMES`, `SEATBELT_CLASS_ID` - constants.

### 2. Code RabbitMQ nằm trong `messaging/`

Không viết code RabbitMQ trong `api/` hoặc `services/`.

### 3. Model file (best_1.pt)

- File model ~700MB, không commit vào git (trong `.gitignore`).
- Phải copy thủ công vào thư mục service trước khi build Docker.
- `MODEL_PATH` trong Docker: `best.pt` (tương đối với WORKDIR `/app`).

---

## Lưu ý về YOLO

### GPU vs CPU

- YOLO mặc định chạy trên CPU trong Docker (không có CUDA).
- Inference time trên CPU: ~200-500ms/frame tùy model.
- Nếu cần GPU: cài `ultralytics[gpu]` và mount GPU trong Docker.

### Memory usage

- YOLO model chiếm ~1-2GB RAM khi load.
- Đảm bảo Docker container có đủ memory limit.

---

## Lưu ý về backward compatibility

### API /check

Endpoint `/check` vẫn hoạt động nhưng implementation đã thay đổi:
- **Trước**: Fetch frame từ Camera-Service → chạy YOLO → trả kết quả.
- **Sau**: Trả về trạng thái mới nhất từ `get_latest_result()`.

Điều này có nghĩa:
- `SeatbeltCheckResponse.detections` sẽ luôn là list rỗng (không có detection details).
- `SeatbeltCheckResponse.inference_time_ms` có thể không chính xác.

### detector_instance.py

File này vẫn tồn tại cho backward compatibility nhưng không còn được sử dụng trực tiếp. Code mới dùng `get_orchestrator().detector`.

---

## Lưu ý về performance

### prefetch_count=1

Consumer chỉ nhận 1 frame mỗi lần. Nếu xử lý chậm, frame sẽ tích tụ trong queue.

### interval từ Camera-Service

Camera-Service gửi frame mỗi `SEATBELT_FRAME_INTERVAL` giây (mặc định 600s). Điều này có nghĩa:
- Seatbelt-Service chỉ xử lý ~1 frame mỗi 10 phút.
- Queue depth thường rất thấp.
- Có thể tăng tần suất bằng cách giảm `SEATBELT_FRAME_INTERVAL`.

---

## Các file không nên sửa

| File | Lý do |
|------|-------|
| `main_detection.py` | Standalone test script, giữ nguyên để tham khảo |
| `best_1.pt` | Model weights |
| `app/utils/logger.py` | Logger đã ổn định |
| `app/schemas/seatbelt.py` | API schemas ổn định |
