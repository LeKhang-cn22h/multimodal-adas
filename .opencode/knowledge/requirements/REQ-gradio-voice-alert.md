# REQ-gradio-voice-alert: Giao diện Gradio + cảnh báo giọng nói

## 1. Actor
- **Tài xế / người giám sát**: nhìn giao diện Gradio hiển thị trạng thái
  real-time (webcam, fatigue level, eye/mouth, seatbelt).
- **Hệ thống ADAS**: nghe cảnh báo giọng nói khi phát hiện nguy hiểm.

## 2. Mục tiêu
1. Xây dựng giao diện web bằng **Gradio** tích hợp trực tiếp vào
   `driver-service`, hiển thị:
   - Video feed từ webcam (real-time).
   - Trạng thái fatigue hiện tại (Awake / Tired / Drowsy / Dangerous).
   - Confidence score.
   - Trạng thái seatbelt (ON/OFF).
2. Khi fatigue level ≥ **Drowsy** (Drowsy hoặc Dangerous), hệ thống tự
   động phát cảnh báo giọng nói tiếng Việt qua loa:
   > "Cảnh báo! Tài xế đang buồn ngủ, hãy dừng xe nghỉ ngơi!"
3. Khi phát hiện **không thắt seatbelt**, hệ thống phát cảnh báo:
   > "Cảnh báo! Vui lòng thắt dây an toàn!"
4. Cảnh báo giọng nói có cơ chế chống lặp (cooldown riêng cho từng loại
   cảnh báo, tránh phát liên tục mỗi frame).

## 3. Ngữ cảnh
- **Driver-service** hiện có:
  - `MessagingOrchestrator`: quản lý vòng đời camera → queue → fatigue
    detector → RabbitMQ publisher.
  - `GET /health`, `GET /stats`, `GET /frame`: API debug.
  - `ClassificationResult`: fatigue_score, fatigue_level (Awake/Tired/
    Drowsy/Dangerous/Unknown), confidence.
  - `CameraCaptureService` (referenced trong orchestrator, đang pending
    implement): background thread mở webcam, đẩy JPEG vào queue.
- **Gradio** sẽ chạy cùng process với FastAPI (phương án A), dùng chung
  `MessagingOrchestrator` singleton để lấy latest frame và latest result.
- **MMS-TTS-VIE**: model TTS tiếng Việt của Facebook (Meta), mã nguồn mở,
  có thể chạy local trên CPU.

## 4. Acceptance Criteria

| # | Tiêu chí |
|---|---------|
| AC-1 | Giao diện Gradio hiển thị webcam feed real-time (JPEG từ camera service) |
| AC-2 | Giao diện hiển thị fatigue level hiện tại (Awake/Tired/Drowsy/Dangerous) kèm màu sắc (xanh/vàng/cam/đỏ) |
| AC-3 | Giao diện hiển thị confidence score dạng % hoặc progress bar |
| AC-4 | Giao diện hiển thị trạng thái seatbelt (nếu có dữ liệu) |
| AC-5 | Khi fatigue level chuyển sang Drowsy hoặc Dangerous → phát giọng nói: "Cảnh báo! Tài xế đang buồn ngủ, hãy dừng xe nghỉ ngơi!" |
| AC-5b | Khi phát hiện không thắt seatbelt → phát giọng nói: "Cảnh báo! Vui lòng thắt dây an toàn!" |
| AC-6 | Mỗi loại cảnh báo có cooldown riêng (mặc định 10s), không phát lại trong khoảng cooldown |
| AC-7 | Giọng nói phát qua loa máy tính (không cần thiết bị ngoài) |
| AC-8 | TTS model load 1 lần khi app khởi động, không load lại mỗi lần phát |
| AC-9 | Gradio UI truy cập được qua browser tại port driver-service (8001) hoặc port phụ |
| AC-10 | Không làm vỡ các API `/health`, `/stats`, `/frame` hiện có |

## 5. Ràng buộc
- **Gradio** và **FastAPI** chạy cùng 1 process, dùng chung singleton
  `get_orchestrator()` để lấy dữ liệu.
- Model MMS-TTS-VIE tải từ HuggingFace hoặc local cache, chạy trên CPU.
- Voice output dùng thư viện `sounddevice` hoặc `pygame` để phát audio.
- Cooldown cảnh báo mặc định 10 giây, có thể config qua env var.
- Nội dung cảnh báo hardcode tiếng Việt (có thể mở rộng sau):
  > "Cảnh báo! Tài xế đang buồn ngủ, hãy dừng xe nghỉ ngơi!"
- Gradio UI không yêu cầu RabbitMQ — hiển thị được ngay cả khi RabbitMQ
  không kết nối.

## 6. Service bị ảnh hưởng
- **driver-service** (port 8001): 
  - Thêm `app/ui/` — module Gradio UI.
  - Sửa `app/main.py` — mount Gradio app vào FastAPI (hoặc chạy thread riêng).
  - Thêm `app/services/voice_alert.py` — TTS + audio playback.
  - Thêm dependency `gradio`, `sounddevice`/`pygame`, `transformers` (cho MMS-TTS).
