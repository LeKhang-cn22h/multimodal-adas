---
description: Đọc toàn bộ .opencode/knowledge/, memory/, summaries/ và code thật trong services/, tái tạo báo cáo "đang ở đâu trong quy trình" sau khi mất phiên làm việc cũ
agent: architect
argument-hint: "(không cần argument)"
---

Đọc TOÀN BỘ các nguồn sau (dùng Read tool cho từng file, không suy đoán):

1. `.opencode/knowledge/requirements/*.md` — liệt kê từng REQ, trạng thái
   (có mục "Quyết định đã chốt"/câu hỏi mở chưa trả lời không).
2. `.opencode/knowledge/features/*.md` — liệt kê từng FEAT, feature nào
   thuộc REQ nào, độ ưu tiên, đã có Tech Solution chưa.
3. `.opencode/knowledge/tech-solutions/*.md` — với MỖI file, đọc kỹ mục
   "Trạng thái xác nhận" ở cuối file: `[ ]` hay `[x]`. Đây là thông tin
   quan trọng nhất — phân loại rõ 3 nhóm: (a) đã xác nhận + đã implement,
   (b) đã xác nhận nhưng CHƯA implement, (c) chưa xác nhận (còn treo).
4. `.opencode/memory/decisions.md` — liệt kê toàn bộ ADR theo thứ tự, ghi
   chú ADR nào đã bị thay thế bởi ADR nào.
5. `.opencode/memory/open-questions.md` — liệt kê nguyên văn các câu hỏi
   còn mở, đây là việc "chưa xong" cần nhắc lại người dùng.
6. `.opencode/summaries/*.md` (nếu có) — đọc summary gần nhất theo ngày.
7. Code thật trong `services/*/app/` — với mỗi file được nhắc tới trong các
   Tech Solution ở nhóm (a)/(b) tại bước 3, kiểm tra file đó THỰC SỰ tồn
   tại trên đĩa và có nội dung khớp mô tả không (không tin lời TS, đối
   chiếu code thật — TS có thể ghi "đã xác nhận" nhưng code thực tế chưa
   được implement đầy đủ, hoặc implement dở dang).

Sau khi đọc xong, trả về báo cáo theo đúng cấu trúc:

## Tổng quan tiến độ
Bảng: REQ -> các FEAT con -> trạng thái TS (chưa có / chưa xác nhận / đã
xác nhận chưa implement / đã implement) -> đối chiếu code thật (khớp / có
sai khác / thiếu file).

## Việc đang dang dở (ưu tiên xử lý trước)
Liệt kê CỤ THỂ: file nào đang chờ xác nhận, câu hỏi nào trong
open-questions.md chưa trả lời, quyết định nào vừa được hỏi trong hội
thoại trước nhưng có thể chưa được ghi lại vào file.

## Đề xuất bước tiếp theo
1 hành động cụ thể, rõ ràng nhất nên làm ngay (không liệt kê nhiều lựa
chọn mơ hồ) — dựa trên đúng vị trí hiện tại trong quy trình 6 bước.

KHÔNG tự ý sửa file nào trong bước này — đây chỉ là bước đọc và báo cáo.