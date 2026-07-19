# Prompt dùng chung: Bối cảnh dự án

Dùng đoạn này khi 1 agent/command cần nhắc lại bối cảnh dự án mà không copy
toàn bộ AGENTS.md.

---

Đây là project MULTIMODAL-ADAS: hệ thống hỗ trợ lái xe nâng cao (ADAS),
kiến trúc microservice, mỗi service là 1 FastAPI app độc lập trong
`services/`. Camera là tài nguyên vật lý dùng chung, chỉ `camera-service`
được mở webcam; mọi service khác lấy frame qua HTTP. Mọi service Python
tuân theo Layered Architecture: `api/ -> services/ -> repositories/`,
`utils/` là pure function không I/O.

Chi tiết đầy đủ: `.opencode/knowledge/architecture.md`,
`.opencode/knowledge/conventions.md`, `.opencode/knowledge/services-map.md`.