---
description: Chuyển yêu cầu thô của người dùng thành Requirement Document chuẩn
agent: architect
argument-hint: "<mô tả yêu cầu thô, ngôn ngữ tự nhiên>"
---

RUN mkdir -p .opencode/knowledge/requirements

Yêu cầu thô từ người dùng:
$USER_REQUEST

Đọc template tại `.opencode/templates/REQ-template.md` (dùng Read tool),
sau đó tạo file `.opencode/knowledge/requirements/REQ-<slug-ngan-gon>.md`
theo đúng cấu trúc của template đó, điền nội dung cụ thể cho yêu cầu trên.

KHÔNG đề xuất giải pháp kỹ thuật ở bước này. Nếu yêu cầu thô còn mơ hồ,
hỏi lại người dùng trước khi viết file (xem thêm
`.opencode/prompts/no-invent-rule.md`).