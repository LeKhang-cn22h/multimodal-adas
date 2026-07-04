# AGENTS.md — MULTIMODAL-ADAS

## 1. Tổng quan dự án

Đồ án ADAS (Advanced Driver Assistance System), kiến trúc **Microservice**,
mỗi service là 1 FastAPI app độc lập.

```
MULTIMODAL-ADAS/
├── frontend/
├── infrastructure/
├── scripts/
├── services/
│   ├── camera-service     # DUY NHẤT được mở webcam
│   ├── driver-service      # MediaPipe Face Landmarker -> fatigue
│   ├── lane-service
│   └── vehicle-service
├── docker-compose.yml
├── AGENTS.md
├── opencode.json
└── .opencode/
    ├── agents/            # định nghĩa agent chuyên biệt
    ├── commands/          # slash command cho từng bước quy trình
    ├── knowledge/         # kiến thức nền: kiến trúc, convention, service map
    │   ├── requirements/  # artifact REQ-*.md (output của /requirement)
    │   ├── features/      # artifact FEAT-*.md (output của /feature)
    │   └── tech-solutions/# artifact TS-*.md (output của /techsolution)
    ├── memory/            # decisions.md (ADR log), open-questions.md
    ├── prompts/           # đoạn prompt tái sử dụng, agent/command include khi cần
    ├── templates/         # template cấu trúc cho REQ/FEAT/TS/DEBUG/SESSION
    ├── debug/             # log điều tra bug (output của /debug)
    ├── summaries/         # tóm tắt phiên làm việc (output của /summary)
    └── README.md          # mô tả cách dùng bộ .opencode/ này
```

Chi tiết trách nhiệm từng service: `.opencode/knowledge/services-map.md`.
Nguyên tắc kiến trúc/coding bắt buộc: `.opencode/knowledge/conventions.md`.

## 2. QUY TRÌNH LÀM VIỆC BẮT BUỘC

Mọi task (tính năng mới, sửa bug, thêm thuật toán...) PHẢI đi qua đủ các bước
sau, theo đúng thứ tự, KHÔNG được nhảy cóc sang "Implement" khi chưa có bước
trước:

```
1. Requirement   -> /requirement   -> .opencode/knowledge/requirements/REQ-<slug>.md
2. Feature       -> /feature       -> .opencode/knowledge/features/FEAT-<slug>.md
3. Tech Solution -> /techsolution  -> .opencode/knowledge/tech-solutions/TS-<slug>.md
4. Logic + AI    -> (nằm trong Tech Solution, mục "Logic + AI")
5. Implement     -> /implement     -> code thật trong services/
6. Test          -> /test          -> test + báo cáo kết quả thật
```

Quy tắc cho từng bước:

- **Requirement**: chỉ diễn giải lại ý người dùng thành yêu cầu có cấu trúc
  (dùng template `.opencode/templates/REQ-template.md`), KHÔNG đề xuất giải
  pháp kỹ thuật, KHÔNG viết code.
- **Feature**: chia Requirement thành các feature nhỏ, mỗi feature độc lập
  triển khai/test được, gắn với đúng 1 service (hoặc rõ ràng nếu liên service).
- **Tech Solution**: chọn công nghệ, thuật toán, thiết kế API/data flow.
  Nếu có phần AI (model, thuật toán CV...), phải nêu rõ input/output, ngưỡng
  (threshold), cách tích hợp vào Layered Architecture hiện có. Đây là bước
  DUY NHẤT được quyết định kiến trúc; Implement không được tự ý đổi.
- **Implement**: chỉ code đúng theo Tech Solution đã duyệt. Nếu phát hiện
  Tech Solution có vấn đề, DỪNG lại, quay về `/techsolution` để cập nhật,
  không tự ý sửa kiến trúc giữa chừng.
- **Test**: viết/chạy unit test + integration test, báo cáo pass/fail rõ
  ràng, không được tự ý coi là "xong" nếu chưa chạy test thật.

Sau khi hoàn tất 1 task, LUÔN chạy `/summary` để ghi lại vào `.opencode/summaries/`.

## 3. Nguồn tri thức (Knowledge Base)

Các file dưới đây được tự động nạp vào context qua `opencode.json -> instructions`.
Không copy nội dung của chúng vào đây để tránh trùng lặp/lệch dữ liệu:

- `.opencode/knowledge/architecture.md` — sơ đồ kiến trúc, luồng dữ liệu
- `.opencode/knowledge/conventions.md` — SOLID, coding style, quy tắc AI
- `.opencode/knowledge/services-map.md` — bảng service, port, API
- `.opencode/memory/decisions.md` — log quyết định kiến trúc đã chốt (ADR)
- `.opencode/memory/open-questions.md` — câu hỏi/rủi ro chưa chốt, PHẢI hỏi
  lại người dùng trước khi giả định, không được tự suy diễn.

## 4. Quy tắc bất di bất dịch

1. Chỉ `camera-service` được gọi `cv2.VideoCapture`. Service khác lấy frame
   qua HTTP `GET /frame` của camera-service.
2. Mỗi service giữ đúng Layered Architecture: `api/ -> services/ -> repositories/`,
   `utils/` là pure function không I/O.
3. Không commit secret, API key, `.env` thật vào git.
4. Trước khi implement bất kỳ thay đổi kiến trúc nào, phải có file
   `.opencode/knowledge/tech-solutions/TS-*.md` tương ứng đã được người
   dùng xác nhận.

## 5. Debug & Summary

- Dùng `/debug` khi gặp lỗi cần điều tra nhiều bước — ghi tiến trình vào
  `.opencode/debug/`, tránh lặp lại hướng đã thử.
- Dùng cờ `opencode -d` khi cần xem debug log cấp hệ thống của chính OpenCode
  (khác với `/debug` — lệnh nghiệp vụ do project này định nghĩa).
- Dùng `/summary` cuối mỗi phiên làm việc để ghi tóm tắt vào `.opencode/summaries/`.