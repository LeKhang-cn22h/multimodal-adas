# Xử lý sự cố - Camera-Service

## RabbitMQ Connection Failed

**Triệu chứng**: Log hiển thị `RabbitMQ connection failed` liên tục.

**Nguyên nhân có thể**:
1. RabbitMQ container chưa chạy.
2. Sai hostname hoặc port.
3. Network không kết nối được (Docker network).
4. Sai credentials.

**Giải pháp**:
```bash
# Kiểm tra RabbitMQ có chạy không
docker ps | grep rabbitmq

# Kiểm tra port
netstat -an | findstr 5672

# Kiểm tra từ trong container camera
docker exec adas-camera ping rabbitmq

# Kiểm tra RabbitMQ Management UI
# Mở browser: http://localhost:15672 (guest/guest)
```

---

## Queue Missing

**Triệu chứng**: Consumer log lỗi `NOT_FOUND - no queue`.

**Nguyên nhân**: Queue chưa được tạo. Publisher không tự tạo queue, chỉ consumer mới tạo.

**Giải pháp**:
- Đảm bảo consumer được start trước hoặc cùng lúc với publisher.
- Hoặc tạo queue thủ công qua Management UI.
- Hoặc thêm `queue_declare` vào publisher (không khuyến nghị).

---

## Frame Decode Error

**Triệu chứng**: Consumer log `Failed to parse driver result`.

**Nguyên nhân**: Message body không phải JSON hợp lệ.

**Giải pháp**:
- Kiểm tra publisher gửi đúng format JSON.
- Kiểm tra xem có ai đang gửi message sai format vào queue không.
- Dùng RabbitMQ Management UI để xem nội dung message trong queue.

---

## Camera Not Opening

**Triệu chứng**: Log `Camera index=0 not available`.

**Nguyên nhân**:
1. Webcam không được kết nối.
2. Webcam đang được ứng dụng khác sử dụng.
3. Docker không có quyền truy cập webcam (Windows).
4. Sai camera index.

**Giải pháp**:
```bash
# Kiểm tra webcam có hoạt động không (Windows)
# Mở Camera app của Windows

# Thử camera index khác
set CAMERA_INDEX=1
python main.py

# Trên Linux, kiểm tra device
ls -la /dev/video*

# Trên Windows, chạy native (không Docker)
cd services/camera-service
python main.py
```

---

## Docker Network Error

**Triệu chứng**: Container không thể kết nối đến `rabbitmq:5672`.

**Nguyên nhân**: Container không nằm trong cùng Docker network.

**Giải pháp**:
```bash
# Kiểm tra network
docker network ls
docker network inspect adas-net

# Đảm bảo cả camera và rabbitmq trong cùng network
docker-compose ps
```

---

## High Memory Usage

**Triệu chứng**: Memory tăng dần theo thời gian.

**Nguyên nhân**: `latest_frame.copy()` tạo bản sao numpy array liên tục.

**Giải pháp**:
- Đây là behavior bình thường. Python GC sẽ dọn dẹp.
- Nếu memory tăng không kiểm soát, kiểm tra display thread có đang chạy không.
- Giảm `FRAME_WIDTH` và `FRAME_HEIGHT` nếu cần.

---

## Display Window Not Showing

**Triệu chứng**: Không thấy cửa sổ "ADAS Monitor".

**Nguyên nhân**:
1. Chạy trong Docker không có X11.
2. Chạy trên server không có màn hình.
3. OpenCV GUI backend không được cài đặt.

**Giải pháp**:
```bash
# Kiểm tra OpenCV có hỗ trợ GUI không
python -c "import cv2; print(cv2.getBuildInformation())" | findstr GUI

# Trên Linux headless, cài đặt Xvfb
apt-get install xvfb
xvfb-run python main.py

# Hoặc tắt display (chỉ chạy capture + publish)
# Sửa code: không gọi display.start() trong orchestrator
```

---

## Log quá nhiều DEBUG message

**Triệu chứng**: Log ngập trong DEBUG messages (vd: `Received frame X`).

**Giải pháp**:
```bash
# Đổi LOG_LEVEL
set LOG_LEVEL=INFO
# hoặc
set LOG_LEVEL=WARNING
```

---

## Port 8005 Already in Use

**Triệu chứng**: `OSError: [Errno 98] Address already in use`.

**Giải pháp**:
```bash
# Tìm process đang dùng port
netstat -ano | findstr :8005

# Kill process
taskkill /PID <PID> /F

# Hoặc dùng port khác
set PORT=8006
python main.py
```
