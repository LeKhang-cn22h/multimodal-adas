# .opencode/ — Agent Workspace cho MULTIMODAL-ADAS

Thư mục này cấu hình OpenCode để làm việc trên project theo quy trình:
**Requirement → Feature → Tech Solution → Logic+AI → Implement → Test**.

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `agents/` | Agent chuyên biệt: `architect` (requirement/feature/techsolution), `coder` (implement), `tester` (test), `reviewer` (review, subagent) |
| `commands/` | Slash command tương ứng từng bước quy trình: `/requirement`, `/feature`, `/techsolution`, `/implement`, `/test`, `/debug`, `/summary` |
| `knowledge/` | Tri thức nền cố định (`architecture.md`, `conventions.md`, `services-map.md`) + artifact động sinh ra khi chạy lệnh (`requirements/`, `features/`, `tech-solutions/`) |
| `memory/` | `decisions.md` (ADR log, append-only), `open-questions.md` (rủi ro/câu hỏi chưa chốt) |
| `prompts/` | Đoạn prompt tái sử dụng giữa nhiều agent/command, tránh lặp nội dung |
| `templates/` | Cấu trúc chuẩn cho từng loại tài liệu (REQ/FEAT/TS/DEBUG/SESSION) |
| `debug/` | Log điều tra bug thật, do `/debug` ghi ra |
| `summaries/` | Tóm tắt phiên làm việc thật, do `/summary` ghi ra |

## Cách dùng

```
/requirement <mô tả yêu cầu thô>
/feature .opencode/knowledge/requirements/REQ-xxx.md
/techsolution .opencode/knowledge/features/FEAT-xxx.md
# xác nhận Tech Solution trước khi qua bước sau
/implement .opencode/knowledge/tech-solutions/TS-xxx.md
/test <tên-service>
/summary
```

Dùng `/debug <mô tả lỗi>` bất cứ lúc nào cần điều tra sự cố nhiều bước.

## Lưu ý

- `knowledge/requirements/`, `knowledge/features/`, `knowledge/tech-solutions/`
  chứa artifact PHÁT SINH theo task — KHÔNG đưa cả 3 thư mục này vào
  `opencode.json -> instructions` (sẽ làm phình context mỗi session);
  chỉ đọc đúng file cần thiết qua Read tool khi command yêu cầu.
- `memory/decisions.md` là append-only — không sửa/xoá entry cũ.
- Cú pháp frontmatter của `agents/*.md` và `commands/*.md` (field
  `mode`, `temperature`, `agent`...) bám theo tài liệu OpenCode tại thời
  điểm soạn bộ này; nếu OpenCode báo lỗi parse khi load, chạy `/init` hoặc
  đối chiếu lại `opencode.ai/docs` vì công cụ cập nhật khá nhanh.