# 🚗 MULTIMODAL-ADAS — Advanced Driver Assistance System

Hệ thống ADAS đa phương thức theo kiến trúc **microservice phân tán**.  
Mỗi thành viên chạy 1 service trên máy của mình, kết nối về máy mạnh chung.

---

## 🏗️ Kiến trúc

```
[Máy A]              [Máy B]             [Máy C]          [Máy D]
driver-service   lane-service      vehicle-service   camera-service
    :8001             :8002               :8004             :8005
       │                │                   │                  │
       └────────────────┴───────────────────┴──────────────────┘
                                    │ POST /event
                              [MÁY MẠNH]
                        aggregator-service :8003
                          api-gateway :8000
                          dashboard   :3000
```

## 📦 Services

| Service | Port | Mô tả | Trạng thái |
|---|---|---|---|
| `api-gateway` | 8000 | Route requests, health check tất cả services | ✅ Ready |
| `aggregator-service` | 8003 | Thu thập + tổng hợp events từ tất cả services | ✅ Ready |
| `driver-service` | 8001 | Phát hiện buồn ngủ qua EAR/MediaPipe | ✅ Ready |
| `lane-service` | 8002 | Phát hiện lệch làn đường | 🚧 Placeholder |
| `vehicle-service` | 8004 | Phát hiện khoảng cách xe phía trước | 🚧 Placeholder |
| `camera-service` | 8005 | Quản lý camera input | 🚧 Placeholder |

---

## 🚀 Bắt đầu nhanh

### Yêu cầu
- Docker + Docker Compose v2
- Git
- (Linux) X11 để hiện cửa sổ OpenCV

### Clone và setup

```bash
git clone https://github.com/YOUR_ORG/MULTIMODAL-ADAS.git
cd MULTIMODAL-ADAS

# Điền IP máy mạnh vào .env
cp .env.example .env
nano .env   # sửa GATEWAY_HOST = IP máy mạnh

# Setup theo role của bạn
bash scripts/setup.sh driver    # nếu bạn làm driver-service
bash scripts/setup.sh gateway   # nếu bạn là máy mạnh
bash scripts/setup.sh all       # chạy tất cả (dev local)
```

### Kiểm tra hệ thống

```bash
# Xem tất cả services có online không
curl http://GATEWAY_HOST:8000/services/health

# Xem trạng thái tổng hợp
curl http://GATEWAY_HOST:8000/api/status

# Xem events gần nhất
curl http://GATEWAY_HOST:8000/api/events?limit=10
```

---

## 🔧 Phân công thành viên

| Thành viên | Service | File chính |
|---|---|---|
| ? | `driver-service` | `services/driver-service/main.py` |
| ? | `lane-service` | `services/lane-service/app/main.py` |
| ? | `vehicle-service` | `services/vehicle-service/app/main.py` |
| ? | `camera-service` | `services/camera-service/app/main.py` |
| ? | `api-gateway` + `aggregator` | `services/api-gateway/`, `services/aggregator-service/` |
| ? | `frontend/dashboard` | `frontend/dashboard/` |

---

## 🌿 Git Workflow

```bash
# Mỗi thành viên làm trên branch riêng
git checkout -b feature/driver-perclos

# Commit xong thì push
git push origin feature/driver-perclos

# Tạo Pull Request lên main
# Code review → merge
```

### Branch naming convention
- `feature/driver-<tên-tính-năng>` — thêm tính năng
- `fix/lane-<tên-bug>` — fix bug
- `docs/<tên>` — cập nhật tài liệu

---

## 📝 API Reference

### Aggregator Service (`:8003`)

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/event` | Nhận event từ service |
| GET | `/events?limit=50&source=driver-service` | Lấy events |
| GET | `/status` | Overall alert level |
| GET | `/stats` | Thống kê phân bố |

### API Gateway (`:8000`)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/health` | Gateway health |
| GET | `/services/health` | Ping tất cả services |
| GET | `/api/status` | Proxy → aggregator/status |
| GET | `/api/events` | Proxy → aggregator/events |
| ANY | `/proxy/{service}/{path}` | Generic proxy |

---

## 🗂️ Cấu trúc project

```
MULTIMODAL-ADAS/
├── services/
│   ├── driver-service/        ← Code driver monitoring
│   ├── lane-service/          ← TODO
│   ├── vehicle-service/       ← TODO
│   ├── camera-service/        ← TODO
│   ├── aggregator-service/    ← Event hub
│   └── api-gateway/           ← Public entry point
├── frontend/dashboard/        ← Streamlit / React dashboard
├── infrastructure/            ← Nginx, network configs
├── scripts/
│   └── setup.sh               ← Quick setup
├── tests/                     ← Integration tests
├── docker-compose.yml         ← Local dev (tất cả trên 1 máy)
├── docker-compose.gateway.yml ← Máy mạnh
├── docker-compose.driver.yml  ← Máy driver
├── .env.example
└── README.md
```

---

## ⚠️ Lưu ý

- File `.env` **KHÔNG được commit** lên GitHub (đã có trong `.gitignore`)
- File `face_landmarker.task` **KHÔNG commit** — script setup sẽ tự download
- Model files (`.pkl`, `.task`) — dùng Git LFS hoặc chia sẻ qua Google Drive