# Coding Conventions & SOLID Checklist

## SOLID áp dụng thực tế trong project này

- **SRP**: 1 file = 1 lý do để thay đổi. Nếu 1 file vừa gọi HTTP vừa tính
  toán AI vừa quyết định business rule -> phải tách.
- **OCP**: thêm thuật toán mới (VD: Yawn counter, Drowsy-driving pattern...)
  = thêm file trong `utils/` + mở rộng `*_service.py`. KHÔNG được sửa `api/`
  hay các client (`camera_client.py`...) để thêm tính năng.
- **LSP**: nếu tạo interface/abstract class cho client (VD: nhiều nguồn
  camera), mọi implementation phải thay thế cho nhau được không vỡ hành vi.
- **ISP**: schema tách theo mục đích dùng (request khác response khác
  internal DTO), không gộp 1 schema khổng lồ dùng cho mọi endpoint.
- **DIP**: `api/` không được `SomeService()` trực tiếp — phải nhận qua
  `Depends(...)` (FastAPI) hoặc constructor injection, wiring tại `main.py`.

## Quy tắc AI/CV bắt buộc

- Mọi thuật toán CV (EAR, MAR, HeadPose, PERCLOS...) là **pure function**
  trong `utils/`: nhận landmarks/mảng số, trả về số/tuple, không random
  side-effect, để unit test bằng dữ liệu giả lập không cần webcam/model thật.
- MediaPipe (hoặc model AI khác) chỉ được gọi trong đúng 1 file
  `services/<tên>_mediapipe_service.py` (hoặc tương đương) — không rải gọi
  model ở nhiều nơi.
- Model chỉ load 1 lần khi app khởi động (trong `lifespan` của `main.py`),
  không load lại mỗi request.
- Threshold/ngưỡng (EAR_THRESHOLD, MAR_THRESHOLD...) luôn đặt trong
  `core/config.py`, không hardcode trong `services/`.

## Quy tắc HTTP client giữa các service

- Camera là service DUY NHẤT mở `cv2.VideoCapture`. Mọi service khác lấy
  frame qua `GET /frame` (image/jpeg) bằng 1 file `*_client.py` riêng trong
  `services/`, dùng `httpx.AsyncClient` tái sử dụng connection pool
  (khởi tạo 1 lần trong `lifespan`, không tạo mới mỗi request).
- Mọi client gọi service khác PHẢI có xử lý lỗi rõ ràng
  (`ServiceUnavailableError` riêng), API layer convert thành `HTTPException`
  với status code phù hợp (503 khi dependency service down).

## Style

- Python: type hint đầy đủ cho public function/method.
- Tên file/module: snake_case. Tên class: PascalCase.
- Mỗi service có `requirements.txt` pin version cụ thể, không dùng version
  range mơ hồ cho các thư viện core (fastapi, mediapipe, opencv...).