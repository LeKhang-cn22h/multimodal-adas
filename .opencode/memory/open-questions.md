# Open Questions / Risks chưa chốt

> Agent thấy mục nào liên quan tới task đang làm thì PHẢI hỏi lại người
> dùng trước khi tự giả định câu trả lời. Khi đã chốt, chuyển thành 1 ADR
> mới trong `memory/decisions.md` và xoá khỏi file này.

- [ ] lane-service và vehicle-service chưa có Tech Solution — chưa rõ
      thuật toán/model dùng cho lane detection, nguồn dữ liệu vehicle
      (CAN bus? mô phỏng?).
- [ ] Frontend gọi trực tiếp từng service hay qua API Gateway chung?
      Chưa chốt — ảnh hưởng tới CORS, auth, aggregation response.
- [ ] Có cần message queue (VD: Redis pub/sub, MQTT) giữa các service AI
      để đồng bộ theo cùng 1 frame timestamp không, hay mỗi service tự
      poll `/frame` độc lập (hiện tại: độc lập, có thể lệch frame nhẹ
      giữa các service)?
- [ ] Chiến lược scale nhiều instance driver-service (nếu cần) — PERCLOS
      hiện lưu in-memory theo từng instance, cần chuyển sang Redis nếu
      chạy nhiều replica đứng sau load balancer.