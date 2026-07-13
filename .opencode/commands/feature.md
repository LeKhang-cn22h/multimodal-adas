---
description: Chia một Requirement Document thành các Feature nhỏ, triển khai/test độc lập được
agent: architect
argument-hint: "<đường dẫn file REQ-*.md trong knowledge/requirements/>"
---

RUN mkdir -p .opencode/knowledge/features

File requirement cần chia nhỏ: $REQUIREMENT_FILE

Đọc file trên và template `.opencode/templates/FEAT-template.md`, sau đó
tạo 1 hoặc nhiều file `.opencode/knowledge/features/FEAT-<slug>.md`, mỗi
file 1 feature độc lập, theo đúng cấu trúc template.

Sau khi tạo xong danh sách feature, hỏi người dùng feature nào làm trước,
rồi gợi ý chạy `/techsolution` cho feature đó.