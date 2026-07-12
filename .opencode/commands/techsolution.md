---
description: Đề xuất Tech Solution (kiến trúc, thuật toán/AI, API) cho một Feature
agent: architect
argument-hint: "<đường dẫn file FEAT-*.md trong knowledge/features/>"
---

RUN mkdir -p .opencode/knowledge/tech-solutions

File feature cần thiết kế giải pháp: $FEATURE_FILE

Đọc file trên, template `.opencode/templates/TS-template.md`, và toàn bộ
`.opencode/knowledge/architecture.md` + `conventions.md` + `services-map.md`,
sau đó tạo `.opencode/knowledge/tech-solutions/TS-<slug>.md` theo đúng cấu
trúc template.

Nếu có điểm chưa chắc chắn, thêm vào `.opencode/memory/open-questions.md`
thay vì tự quyết định. Nếu thêm/đổi API, cập nhật
`.opencode/knowledge/services-map.md`.

Sau khi viết xong, để nguyên mục "Trạng thái xác nhận" ở `[ ] Chưa xác nhận`
và YÊU CẦU người dùng xác nhận trước khi cho phép `/implement` dùng file
này.