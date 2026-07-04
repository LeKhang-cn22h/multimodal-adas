# Bảng service — MULTIMODAL-ADAS

> Agent PHẢI cập nhật file này ngay khi thêm/đổi service, port, hoặc API
> endpoint mới. Đây là nguồn sự thật duy nhất cho "service nào làm gì".

| Service | Port (đề xuất) | Trách nhiệm chính | API chính | Ghi chú |
|---|---|---|---|---|
| camera-service | 8005 | Mở webcam DUY NHẤT, đọc frame liên tục qua background thread, encode JPEG, giữ `latest_frame`/`latest_jpeg` trong RAM | `GET /frame`, `GET /health`, `GET /info`, `GET /stats` | KHÔNG làm AI |
| driver-service | 8006 (đề xuất) | Lấy frame từ camera-service, chạy MediaPipe Face Landmarker, tính EAR/MAR/HeadPose/PERCLOS/Blink, phân loại fatigue | `GET /fatigue`, `GET /fatigue/health` | Không tự mở webcam |
| lane-service | TBD | Phát hiện làn đường | TBD | Cần bổ sung khi có Tech Solution |
| vehicle-service | TBD | Thông tin/telemetry xe | TBD | Cần bổ sung khi có Tech Solution |
| frontend | TBD | Hiển thị dashboard tổng hợp | - | Gọi các service qua API Gateway hoặc trực tiếp (cần chốt trong Tech Solution) |

## Quy ước đặt port

- Mỗi service 1 port cố định, khai báo trong `docker-compose.yml` và đồng bộ
  với bảng trên. Không để 2 service trùng port trong cùng network.

## Quy ước network Docker

- Tất cả service nằm chung 1 network nội bộ (VD: `adas-net`) để gọi nhau
  qua service name (VD: `http://camera-service:8005`), không dùng IP cứng.