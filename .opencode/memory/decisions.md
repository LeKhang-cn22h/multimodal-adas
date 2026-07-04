# Decision Log (ADR ngắn gọn)

> Append-only. Mỗi quyết định kiến trúc quan trọng thêm 1 entry mới ở CUỐI
> file, KHÔNG sửa/xoá entry cũ (nếu quyết định đổi, thêm entry mới ghi rõ
> "thay thế ADR-00X"). Agent PHẢI đọc file này trước khi đề xuất kiến trúc
> để không đề xuất lại thứ đã bị bác bỏ.

## ADR-001: Driver Service không tự mở webcam

- **Ngày**: (điền khi áp dụng thật)
- **Bối cảnh**: Ban đầu driver-service dùng `cv2.VideoCapture(0)` trực tiếp,
  xung đột với camera-service khi cả 2 cùng chạy.
- **Quyết định**: Driver Service lấy frame qua `GET /frame` của
  camera-service bằng `services/camera_client.py`. Camera-service là service
  DUY NHẤT được mở webcam.
- **Hệ quả**: Thêm 1 network hop mỗi lần lấy frame; đổi lại tránh xung đột
  tài nguyên phần cứng và giữ đúng ranh giới microservice.

## ADR-002: Artifact quy trình (REQ/FEAT/TS) lưu trong .opencode/knowledge/

- **Ngày**: (điền khi áp dụng thật)
- **Bối cảnh**: Cần chọn nơi lưu file sinh ra bởi /requirement, /feature,
  /techsolution.
- **Quyết định**: Lưu trong `.opencode/knowledge/requirements/`,
  `.opencode/knowledge/features/`, `.opencode/knowledge/tech-solutions/`
  thay vì 1 thư mục `docs/` riêng ở root.
- **Hệ quả**: Toàn bộ tri thức project (kiến trúc cố định + artifact theo
  từng task) nằm chung dưới `.opencode/knowledge/`, dễ nạp vào context qua
  `opencode.json -> instructions` nếu cần mở rộng sau này, nhưng cần lưu ý
  KHÔNG add cả thư mục requirements/features/tech-solutions vào
  `instructions` mặc định (sẽ phình context) — chỉ đọc theo yêu cầu (Read
  tool) khi command cần đúng 1 file cụ thể.

<!-- Thêm ADR mới bên dưới dòng này -->