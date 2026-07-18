# FEAT-label-tool: Labeling Tool GUI cho ADAS Dataset

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-label-tool.md`

## Service
Không thuộc service nào — standalone tool `scripts/label_tool.py`.

## Mô tả chức năng
Ứng dụng desktop Python (customtkinter) hỗ trợ gán nhãn ảnh cho dataset ADAS với 5 thuộc tính: Eye (open/close), Glass (glass/noglass), Face (face/noface), Yawn (yawn/noyawn), Seatbelt (seatbelt/noseatbelt). Tool đọc thư mục ảnh, hiển thị từng ảnh kèm radio button, preview tên file mới theo naming convention, và rename file tại chỗ khi lưu.

## Acceptance Criteria
- AC1: Open Folder → load toàn bộ ảnh, hiển thị ảnh đầu tiên.
- AC2: Ảnh fit cửa sổ không méo, resize responsive.
- AC3: 5 nhóm radio button chọn label, preview tên mới realtime.
- AC4: Parse tên file có dạng `{eye}_{glass}_{face}_{yawn}_{seatbelt}_{XXXX}.{ext}` → radio tự chọn đúng.
- AC5: Save → rename file với số tự động tăng, không ghi đè.
- AC6: Save & Next → rename + chuyển ảnh kế tiếp.
- AC7: Previous/Next → chuyển ảnh kèm cập nhật radio.
- AC8: Phím tắt: ← → Enter 1-9 0 Ctrl+O Ctrl+S.
- AC9: Preview tên file mới, tên file hiện tại, tiến độ, status bar.
- AC10: Dark mode, giao diện hiện đại.

## Độ ưu tiên
**P0** — Công cụ cần thiết để tạo dataset cho các model ADAS.

## Phụ thuộc
Không.
