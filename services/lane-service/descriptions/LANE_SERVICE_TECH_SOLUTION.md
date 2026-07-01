# 🛣️ Lane Service — Kế hoạch triển khai và bàn giao tiếp tục

## 1. Mục tiêu

Xây dựng `lane-service` cho dự án **MULTIMODAL-ADAS** theo hướng microservice độc lập.

Kiến trúc kỹ thuật cuối cùng của phần nhận diện làn đường:

```text
Video / Frame
    ↓
YOLOv11
Nhận diện phương tiện và vật cản
    ↓
DeepLabV3+
Phân vùng mặt đường và vạch làn
    ↓
OpenCV
Xử lý hình học, tính tâm làn và độ lệch
    ↓
Lane Offset + Hướng lệch
    ↓
Gửi event sang aggregator-service
```

Nguồn dữ liệu nền tảng dự kiến sử dụng:

```text
BDD100K
```

Sau đó có thể fine-tune bằng dữ liệu giao thông Việt Nam.

---

## 2. Trạng thái hiện tại

Thư mục hiện có:

```text
services/
└── lane-service/
    ├── app/
    │   └── main.py
    ├── Dockerfile
    └── requirements.txt
```

`main.py` hiện mới có API kiểm tra:

```http
GET /health
```

Service chạy tại:

```text
Port: 8002
```

Kết quả kiểm tra:

```json
{
  "status": "ok",
  "service": "lane-service"
}
```

---

## 3. Nguyên tắc triển khai

- Chỉ sửa bên trong `services/lane-service/`.
- Không tự ý thay đổi service khác.
- Mỗi service là một luồng độc lập.
- `lane-service` tự quản lý code inference, model, training và kết quả riêng.
- Không đưa dataset lớn hoặc model lớn lên GitHub bằng Git thông thường.
- Phần API runtime và phần training phải tách rõ ràng.
- Chưa tích hợp toàn bộ YOLO, DeepLab và OpenCV cùng một lúc.
- Thực hiện theo từng checkpoint nhỏ để dễ kiểm tra.

---

## 4. Cấu trúc dự kiến của lane-service

```text
services/
└── lane-service/
    ├── app/
    │   ├── main.py
    │   ├── config.py
    │   ├── schemas.py
    │   ├── video_source.py
    │   ├── pipeline.py
    │   ├── event_client.py
    │   │
    │   ├── core/
    │   │   ├── __init__.py
    │   │   ├── yolo_detector.py
    │   │   ├── deeplab_segmenter.py
    │   │   ├── fusion.py
    │   │   └── geometry.py
    │   │
    │   └── utils/
    │       ├── __init__.py
    │       └── visualization.py
    │
    ├── training/
    │   ├── prepare_bdd100k.py
    │   ├── train_yolo.py
    │   ├── train_deeplab.py
    │   ├── evaluate.py
    │   └── export_models.py
    │
    ├── data/
    │   ├── README.md
    │   └── .gitkeep
    │
    ├── models/
    │   ├── README.md
    │   └── .gitkeep
    │
    ├── outputs/
    │   └── .gitkeep
    │
    ├── Dockerfile
    ├── requirements.txt
    ├── requirements-train.txt
    └── README.md
```

Chưa cần tạo toàn bộ cùng lúc. Chỉ tạo file theo đúng giai đoạn đang làm.

---

## 5. Vai trò của từng thành phần

### `app/main.py`

FastAPI entry point.

Dự kiến có:

```http
GET  /health
POST /analyze-video
POST /analyze-frame
```

Không đặt toàn bộ thuật toán trong file này.

### `app/video_source.py`

Phụ trách:

- Mở video.
- Đọc từng frame.
- Đọc video upload trực tiếp.
- Sau này có thể đọc video URL từ `video-service`.
- Giải phóng `cv2.VideoCapture`.

### `app/pipeline.py`

Điều phối luồng xử lý:

```text
Frame
→ YOLO
→ DeepLabV3+
→ Fusion
→ OpenCV Geometry
→ Kết quả
```

### `app/core/yolo_detector.py`

Dùng YOLOv11 để phát hiện:

- Xe máy.
- Ô tô.
- Xe tải.
- Xe buýt.
- Vật cản.

### `app/core/deeplab_segmenter.py`

Dùng DeepLabV3+ để tạo mask:

- Background.
- Drivable area.
- Lane marking.

### `app/core/fusion.py`

Kết hợp kết quả YOLO và DeepLabV3+.

Ví dụ:

- Xác định vùng làn bị phương tiện che.
- Loại vùng vật cản khỏi vùng đường an toàn.
- Chuẩn bị mask sạch cho OpenCV.

### `app/core/geometry.py`

Dùng OpenCV để:

- Làm sạch mask.
- Tìm biên làn trái và phải.
- Tính tâm làn.
- Tính tâm xe hoặc tâm ảnh.
- Tính `lane_offset`.
- Xác định `LEFT`, `RIGHT`, `CENTER`.

### `app/event_client.py`

Gửi cảnh báo đến:

```text
POST http://aggregator-service:8003/event
```

Dạng dữ liệu dự kiến:

```json
{
  "source": "lane-service",
  "alert_level": "DROWSY",
  "lane_offset": 0.24,
  "data": {
    "direction": "left",
    "message": "Lane departure detected"
  }
}
```

---

## 6. Checkpoint đầu tiên phải làm

Chưa làm AI ngay.

Mục tiêu đầu tiên:

```text
Nhận video
→ đọc được video
→ lấy frame
→ chạy pipeline rỗng
→ trả kết quả API
```

Kết quả mong muốn:

```json
{
  "status": "ok",
  "service": "lane-service",
  "video": {
    "fps": 30,
    "total_frames": 900,
    "width": 1280,
    "height": 720
  },
  "frames_processed": 30
}
```

---

## 7. Các file cần tạo đầu tiên

Chỉ tạo trước:

```text
services/lane-service/app/config.py
services/lane-service/app/schemas.py
services/lane-service/app/video_source.py
services/lane-service/app/pipeline.py
```

Tạo thêm thư mục:

```text
services/lane-service/app/core/
services/lane-service/app/utils/
```

Chưa cần viết YOLO và DeepLab thật trong checkpoint đầu.

---

## 8. Requirements giai đoạn đầu

`services/lane-service/requirements.txt`:

```text
fastapi==0.111.0
uvicorn[standard]==0.30.1
opencv-python-headless==4.10.0.84
numpy
python-multipart==0.0.9
httpx
```

Ý nghĩa:

- `fastapi`: API.
- `uvicorn`: chạy service.
- `opencv-python-headless`: đọc và xử lý video trong Docker.
- `numpy`: xử lý ảnh.
- `python-multipart`: nhận file upload.
- `httpx`: gửi event sang aggregator sau này.

Chưa thêm ngay:

```text
torch
torchvision
ultralytics
segmentation-models-pytorch
```

Các thư viện nặng này sẽ thêm ở giai đoạn AI.

---

## 9. Luồng API đầu tiên

Endpoint:

```http
POST /analyze-video
```

Cách hoạt động:

```text
Postman upload file MP4
    ↓
main.py lưu file tạm
    ↓
video_source.py mở video
    ↓
pipeline.py xử lý một số frame
    ↓
trả JSON
    ↓
xóa file tạm
```

Không lưu video lâu dài trong `lane-service`.

---

## 10. Kiểm tra bằng Docker

Build:

```powershell
docker compose build lane-service
```

Chạy:

```powershell
docker compose up -d lane-service
```

Kiểm tra trạng thái:

```powershell
docker compose ps lane-service
```

Xem log:

```powershell
docker compose logs -f lane-service
```

Kiểm tra health:

```powershell
curl.exe http://127.0.0.1:8002/health
```

---

## 11. Kiểm tra bằng Postman

### Health check

```text
GET http://127.0.0.1:8002/health
```

### Upload video

```text
POST http://127.0.0.1:8002/analyze-video
```

Trong Postman:

```text
Body
→ form-data
→ Key: file
→ Type: File
→ Chọn video MP4
```

---

## 12. Thứ tự tích hợp AI

Làm lần lượt:

```text
1. Video input hoạt động
2. Pipeline rỗng hoạt động
3. OpenCV geometry với mask thử
4. DeepLabV3+ tạo mask thật
5. Tính lane_offset
6. YOLOv11 phát hiện phương tiện và vật cản
7. Fusion YOLO + DeepLab
8. Gửi event sang aggregator-service
9. Chuẩn bị BDD100K
10. Train hoặc fine-tune model
11. Fine-tune dữ liệu Việt Nam
```

DeepLabV3+ làm trước YOLO vì nhiệm vụ chính của `lane-service` là phân vùng làn và tính độ lệch.

---

## 13. Phần training và dataset

Training vẫn nằm riêng trong:

```text
services/lane-service/training/
```

Dataset nằm trong:

```text
services/lane-service/data/
```

Nhưng dữ liệu thật không được commit lên GitHub.

Model sau train nằm trong:

```text
services/lane-service/models/
```

Ví dụ:

```text
yolo11_bdd100k.pt
deeplabv3plus_bdd100k.pth
```

Các file model lớn nên dùng:

- Google Drive.
- Git LFS.
- OneDrive.
- Script tải model khi setup.

---

## 14. `.gitignore` nên bổ sung

```gitignore
services/lane-service/data/*
!services/lane-service/data/README.md
!services/lane-service/data/.gitkeep

services/lane-service/models/*.pt
services/lane-service/models/*.pth
services/lane-service/models/*.onnx
services/lane-service/models/*.engine

services/lane-service/outputs/*
!services/lane-service/outputs/.gitkeep

services/lane-service/**/__pycache__/
```

---

## 15. Những việc chưa làm

Chưa làm các việc sau:

- Chưa tải toàn bộ BDD100K.
- Chưa train YOLOv11.
- Chưa train DeepLabV3+.
- Chưa tích hợp model `.pt` hoặc `.pth`.
- Chưa viết fusion.
- Chưa gửi event thật sang aggregator.
- Chưa thay đổi service khác.
- Chưa chốt cách lấy video từ `video-service`.

Hiện tại có thể tạm cho `lane-service` nhận video trực tiếp. Sau khi nhóm trưởng thống nhất, chỉ cần đổi `video_source.py` để lấy video URL từ `video-service`.

---

## 16. Việc cần làm tiếp theo trong buổi sau

Bắt đầu từ checkpoint đầu tiên:

```text
1. Tạo video_source.py
2. Tạo pipeline.py
3. Cập nhật requirements.txt
4. Thêm POST /analyze-video vào main.py
5. Build Docker
6. Test bằng Postman
```

Khi upload video và đọc frame thành công mới chuyển sang `geometry.py` và DeepLabV3+.
