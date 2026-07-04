# Quy ước code - Seatbelt-Service

Áp dụng các quy ước chung của dự án (xem Camera-Service `knowledge-base/coding_guidelines.md`).

## Quy tắc riêng cho Seatbelt-Service

### 1. KHÔNG sửa code YOLO

Các phương thức `_run_inference()`, `_decode_jpeg()`, `_update_stats()`, `load_model()` được đánh dấu "KEPT EXACTLY AS IS" - không thay đổi.

### 2. Constants YOLO

```python
CLASS_NAMES = {0: "cell phone", 1: "drinking", ..., 6: "seatbelt"}
SEATBELT_CLASS_ID = 6
```

Không thay đổi class mapping.

### 3. Backward compatibility

- API `/check` vẫn hoạt động (dùng `get_latest_result()`).
- `detector_instance.py` vẫn tồn tại.

### 4. Naming convention

- File: `snake_case` (seatbelt_detector.py).
- Class: `PascalCase` (SeatbeltDetector).
- Method: `snake_case` (load_model, get_stats).
- Private: prefix `_` (_run_inference, _update_stats).
