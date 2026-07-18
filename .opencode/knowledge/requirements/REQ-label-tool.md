# REQ-label-tool: Labeling Tool cho ADAS Dataset

## 1. Actor
- **Data Engineer / Developer** — người gán nhãn cho ảnh dataset ADAS.

## 2. Mục tiêu
Tạo công cụ desktop gán nhãn ảnh cho dataset ADAS với 5 thuộc tính (Eye, Glass, Face, Yawn, Seatbelt). Công cụ đọc thư mục ảnh, hiển thị từng ảnh, cho phép gán nhãn qua radio button, preview tên file mới, và lưu bằng cách rename file theo naming convention.

## 3. Ngữ cảnh
- Standalone tool, không phụ thuộc các service ADAS.
- Chạy local trên máy developer.
- File output được rename tại chỗ trong thư mục ảnh.

## 4. Acceptance Criteria
- AC1: Mở được thư mục chứa ảnh (jpg, jpeg, png, bmp, webp).
- AC2: Hiển thị ảnh fit cửa sổ, không méo, resize theo cửa sổ.
- AC3: 5 nhóm radio button (Eye, Glass, Face, Yawn, Seatbelt).
- AC4: Preview tên file mới cập nhật realtime theo radio button.
- AC5: Naming convention: `{eye}_{glass}_{face}_{yawn}_{seatbelt}_{XXXX}.{ext}`
- AC6: Tự động tìm số tiếp theo, không ghi đè.
- AC7: Save → rename file; Save & Next → rename rồi chuyển ảnh kế.
- AC8: Đọc label từ tên file có sẵn (parse filename).
- AC9: Hiển thị tiến độ (current/total), tên file, status bar.
- AC10: Dark mode + customtkinter.
- AC11: Phím tắt đầy đủ (← → Enter 1-9 0 Ctrl+O Ctrl+S).
- AC12: Không crash với thư mục rỗng hoặc tên trùng.

## 5. Ràng buộc
- Python 3.11+, customtkinter, Pillow.
- 1 file duy nhất: `label_tool.py`.
- Không Qt/PySide/PyQt.
- PEP8, type hint, OOP, không global variable.

## 6. Service bị ảnh hưởng
Không — tool standalone, đặt trong `scripts/label_tool.py`.
