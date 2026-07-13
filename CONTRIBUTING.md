# 🤝 Hướng dẫn đóng góp — MULTIMODAL-ADAS

## Setup lần đầu

```bash
git clone https://github.com/YOUR_ORG/MULTIMODAL-ADAS.git
cd MULTIMODAL-ADAS
cp .env.example .env
# Điền GATEWAY_HOST = IP máy mạnh vào .env
bash scripts/setup.sh <role-của-bạn>
```

## Quy trình làm việc

```bash
# 1. Luôn pull mới nhất trước khi làm
git pull origin main

# 2. Tạo branch mới
git checkout -b feature/ten-tinh-nang

# 3. Code... test...

# 4. Commit với message rõ ràng
git add .
git commit -m "feat(driver): thêm PERCLOS vào feature extractor"

# 5. Push và tạo PR
git push origin feature/ten-tinh-nang
```

## Commit message format

```
<type>(<service>): <mô tả ngắn>

type: feat | fix | docs | refactor | test | chore
service: driver | lane | vehicle | camera | aggregator | gateway | dashboard
```

Ví dụ:
- `feat(driver): thêm MAR để phát hiện ngáp`
- `fix(aggregator): sửa lỗi timeout khi service offline`
- `docs(readme): cập nhật hướng dẫn setup`

## Test trước khi tạo PR

```bash
# Test service của bạn
docker compose -f docker-compose.<service>.yml up --build

# Kiểm tra health
curl http://localhost:<PORT>/health

# Gửi event test lên aggregator
curl -X POST http://GATEWAY_HOST:8003/event \
  -H "Content-Type: application/json" \
  -d '{"source":"driver-service","alert_level":"DROWSY","ear":0.18}'
```

## Thêm endpoint mới vào service của bạn

1. Thêm route vào `services/<your-service>/app/main.py`
2. Cập nhật API Reference trong `README.md`
3. Nếu cần expose qua gateway → thêm route vào `api-gateway/app/main.py`

## Câu hỏi?

Tạo Issue trên GitHub hoặc hỏi trong nhóm chat!