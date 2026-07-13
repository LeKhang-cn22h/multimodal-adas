---
description: Đọc code thật của 1 hoặc nhiều service, đối chiếu với knowledge base hiện có, báo cáo điểm khớp/lệch, KHÔNG tự sửa code hay tự chốt kiến trúc
agent: architect
argument-hint: "<danh sách đường dẫn service cần đọc>"
---

Đường dẫn service cần đọc: $SERVICE_PATHS

Nhiệm vụ: đọc toàn bộ code trong các đường dẫn trên (cấu trúc thư mục, file
chính, requirements.txt/Dockerfile, docker-compose liên quan) để hiểu hiện
trạng THẬT của hệ thống, sau đó đối chiếu với:
- `.opencode/knowledge/architecture.md`
- `.opencode/knowledge/services-map.md`
- `.opencode/memory/decisions.md`

Báo cáo theo đúng cấu trúc sau, KHÔNG tự sửa code, KHÔNG tự sửa knowledge
base trong bước này:

## 1. Cấu trúc thực tế đã đọc được
Liệt kê cây thư mục, các file/module chính, dependency chính (từ
requirements.txt), cơ chế giao tiếp thực tế đang dùng (HTTP? message
queue? cả hai?).

## 2. Điểm KHỚP với knowledge base hiện có
Những gì code thật đúng với `architecture.md`/`services-map.md` đã ghi.

## 3. Điểm LỆCH / MÂU THUẪN
Những gì code thật khác với knowledge base hoặc khác với ADR đã chốt trong
`decisions.md`. Với mỗi điểm lệch, nêu rõ: hiện trạng code là gì, tài liệu
đang ghi là gì, và tại sao đây là mâu thuẫn cần người dùng quyết định (không
tự chọn bên nào đúng).

## 4. Đề xuất cập nhật (chờ xác nhận)
Đề xuất các dòng cần sửa trong `services-map.md`/`architecture.md`, và/hoặc
1 ADR mới cần thêm vào `decisions.md` — nhưng CHỈ viết ra đề xuất, chờ người
dùng xác nhận rồi mới thực sự sửa file.

## 5. Câu hỏi cần hỏi lại người dùng
Bất kỳ điểm nào không thể suy luận chắc chắn từ code (VD: RabbitMQ dùng để
làm gì — truyền frame, hay việc khác như logging/event?), liệt kê thành câu
hỏi cụ thể, không tự đoán.