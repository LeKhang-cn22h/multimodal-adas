# FEAT-remove-headpose-drowsiness-level: Dọn dẹp DrowsinessLevel enum & LEVEL_DISPLAY

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-remove-headpose.md`

## Service
`driver-service` — file `app/models/drowsiness_level.py`

## Mô tả chức năng
Đơn giản hóa `DrowsinessLevel` enum từ 6 giá trị xuống còn 4, phản ánh đúng trạng thái thực tế của pipeline sau khi loại bỏ Head Pose:

- `NORMAL` — Driver tỉnh táo (giữ nguyên).
- `DROWSY` — Driver buồn ngủ (gộp từ `DROWSY_MILD` + `DROWSY_SEVERE` + `YAWNING`).
- `NO_FACE` — Không phát hiện khuôn mặt (giữ nguyên).
- `FACE_DETECTED_BUT_INVALID` — Có khuôn mặt nhưng không crop được mắt/miệng (mới).

Xóa: `LOOKING_AWAY`, `YAWNING`, `DROWSY_MILD`, `DROWSY_SEVERE`.

Cập nhật `LEVEL_DISPLAY` dict tương ứng.

## Acceptance Criteria
- AC1: `DrowsinessLevel` enum chỉ chứa `NORMAL`, `DROWSY`, `NO_FACE`, `FACE_DETECTED_BUT_INVALID`.
- AC2: `LEVEL_DISPLAY` có đúng 4 entry, mỗi entry có `text` và `color` phù hợp.
- AC3: Không còn reference đến `LOOKING_AWAY`, `YAWNING`, `DROWSY_MILD`, `DROWSY_SEVERE` trong file này.
- AC4: Các file khác import `DrowsinessLevel` vẫn hoạt động sau khi đổi (cần cập nhật đồng bộ).

## Độ ưu tiên
**P0** — Đây là thay đổi nền tảng, mọi component khác phụ thuộc vào enum này.

## Phụ thuộc
Không phụ thuộc feature nào khác, nhưng các feature refactor Rule Engine và DrowsinessDetector PHẢI chạy sau feature này.
