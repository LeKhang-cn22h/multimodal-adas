---
description: Implement code đúng theo một Tech Solution đã được xác nhận
agent: coder
argument-hint: "<đường dẫn file TS-*.md trong knowledge/tech-solutions/>"
---

File Tech Solution cần implement: $TECH_SOLUTION_FILE

Bắt buộc trước khi sửa file nào trong services/:
1. Đọc $TECH_SOLUTION_FILE bằng Read tool.
2. Kiểm tra mục "Trạng thái xác nhận" trong file đó. Nếu là
   `[ ] Chưa xác nhận` -> DỪNG LẠI, báo người dùng cần xác nhận trước.
3. Đọc `.opencode/knowledge/conventions.md`.

Sau đó implement từng bước, mỗi bước 1 file, giải thích ngắn gọn trách
nhiệm file đó trước khi viết (không viết tắt, không bỏ bước, đúng tinh
thần Layered Architecture đã mô tả).

Khi xong, liệt kê danh sách file đã tạo/sửa, và đề nghị chạy `/test`.