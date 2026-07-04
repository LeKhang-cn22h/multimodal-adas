---
description: Tóm tắt phiên làm việc hiện tại, ghi vào .opencode/summaries/ và cập nhật memory nếu có quyết định mới
---

RUN mkdir -p .opencode/summaries

Tóm tắt lại toàn bộ session hiện tại thành file
`.opencode/summaries/SESSION-<ngày>-<slug>.md`, dựa theo
`.opencode/templates/SESSION-template.md`.

Nếu có quyết định kiến trúc mới chốt trong session này, thêm 1 entry mới
vào CUỐI file `.opencode/memory/decisions.md` (đúng format ADR đã có,
KHÔNG sửa entry cũ). Nếu có câu hỏi cũ trong
`.opencode/memory/open-questions.md` đã được trả lời trong session này,
xoá khỏi file đó (vì đã chuyển thành ADR).