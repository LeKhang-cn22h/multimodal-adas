---
description: Viết và chạy test cho một service, báo cáo kết quả thật
agent: tester
argument-hint: "<tên service, VD: driver-service>"
---

Service cần test: $SERVICE_NAME

1. Xác định thư mục `services/$SERVICE_NAME/`.
2. Nếu chưa có thư mục `tests/`, tạo mới, theo cấu trúc tương ứng `app/`
   (VD: `tests/utils/test_ear.py` cho `app/utils/ear.py`).
3. Viết test theo quy tắc trong `.opencode/agents/tester.md` (mock
   dependency ngoài, test riêng pure function, test business logic bằng
   dữ liệu giả lập).

RUN cd services/$SERVICE_NAME && python -m pytest -v || true

Báo cáo kết quả pytest thật (pass/fail/error), không suy đoán. Nếu fail,
liệt kê rõ từng lỗi và đề xuất hướng sửa, giao lại cho `/implement` xử lý
thay vì tự sửa logic nghiệp vụ.