---
description: Điều tra lỗi có hệ thống, ghi lại tiến trình vào .opencode/debug/
agent: coder
argument-hint: "<mô tả lỗi/triệu chứng>"
---

RUN mkdir -p .opencode/debug

Mô tả lỗi/triệu chứng: $ISSUE_DESCRIPTION

Quy trình bắt buộc:
1. Kiểm tra xem đã có file `.opencode/debug/DEBUG-<slug>.md` cho lỗi này
   chưa (tránh lặp lại hướng điều tra đã thử).
2. Nếu chưa có, tạo file mới dựa theo `.opencode/templates/DEBUG-template.md`.
3. Mỗi lần thử 1 giả thuyết, CẬP NHẬT file này ngay (append), không chờ
   tới khi xong mới ghi — để nếu bị ngắt giữa chừng, session sau đọc lại
   không mất tiến trình.
4. Ưu tiên tái hiện lỗi bằng test trước khi sửa (viết test fail trước,
   sửa code, chạy lại test để xác nhận pass).

Khi tìm ra nguyên nhân gốc, hỏi người dùng có muốn fix ngay hay quay lại
`/techsolution` nếu nguyên nhân là do thiết kế sai.