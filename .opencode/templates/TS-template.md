# TS-<slug>: <tên>

## Thuộc Feature
Tham chiếu FEAT tương ứng (đường dẫn trong `.opencode/knowledge/features/`).

## Kiến trúc
Sơ đồ luồng dữ liệu (text-based), các file/layer sẽ tạo/sửa
(api/, services/, repositories/, utils/, schemas/) và trách nhiệm từng file.
Phải khớp `.opencode/knowledge/architecture.md`.

## Logic + AI (nếu có)
- Thuật toán/model dùng (tên, nguồn, license nếu có)
- Input/output chính xác (kiểu dữ liệu, shape, đơn vị)
- Ngưỡng (threshold) và lý do chọn giá trị đó
- Độ phức tạp/hiệu năng ước tính (frame/s, latency)

## API Contract
Endpoint, method, request/response schema (map sang Pydantic model cụ thể).

## Rủi ro & câu hỏi mở
Nếu có điểm chưa chắc chắn, thêm vào `.opencode/memory/open-questions.md`
thay vì tự quyết định.

## Ảnh hưởng tới service khác
Cập nhật `.opencode/knowledge/services-map.md` nếu thêm/đổi API.

## Trạng thái xác nhận
`[ ] Chưa xác nhận` / `[x] Đã xác nhận bởi người dùng ngày ___` — chỉ được
`/implement` khi mục này đã tick.