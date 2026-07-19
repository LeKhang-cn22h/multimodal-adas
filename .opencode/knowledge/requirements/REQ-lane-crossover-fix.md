# REQ-lane-crossover-fix: Khắc phục lỗi giao cắt đường biên làn (X-Crossing)

## 1. Actor
- **Tài xế**: Nhận thông tin cảnh báo lệch làn chính xác hơn, không bị rối loạn hình ảnh do vạch kẻ hiển thị chéo.
- **Hệ thống giám sát ADAS**: Tránh gửi cảnh báo lệch làn sai lệch do hai đường biên trái/phải bị cắt chéo nhau.

## 2. Mục tiêu
- Loại bỏ hoàn toàn hiện tượng hiển thị 2 đường biên làn chéo nhau thành hình chữ X khi có nhiễu ở lòng đường hoặc vỉa hè.
- Đảm bảo khi phát hiện giao cắt, hệ thống tự động loại bỏ các đường biên bị sai lệch, chỉ vẽ vùng di chuyển an toàn (Drivable Area) hoặc sử dụng lịch sử ổn định (EMA) để bù đắp.

## 3. Ngữ cảnh
- Nằm trong `lane-service` tại `services/lane-service/app/core/geometry.py`.
- Lỗi xảy ra khi thuật toán Sliding Window khớp đa thức bậc 2 cho hai làn trái/phải riêng biệt, nhưng do nhiễu, các đường này hội tụ hoặc cắt chéo nhau trên ảnh (dạng chữ X).

## 4. Acceptance Criteria
- **GIVEN** Luồng video đầu vào từ camera.
- **WHEN** Khớp đa thức làn đường trái và phải mà hai đường này cắt nhau tại bất kỳ điểm nào trong vùng hiển thị (đặc biệt trong khoảng từ `y_top` đến `y_bot` hoặc toàn bộ `ploty`).
- **THEN** Hệ thống phát hiện sự giao cắt, từ chối cập nhật đa thức lỗi này, đồng thời:
  - Sử dụng lại dữ liệu lịch sử ổn định từ bộ đệm EMA (nếu có lịch sử).
  - Hoặc nếu không có lịch sử, trả về `lane_detected: False`, không hiển thị đường biên lỗi lên màn hình HUD (chỉ giữ lại vùng xanh drivable area).

## 5. Ràng buộc
- Phải đảm bảo kiểm tra giao cắt trên toàn bộ tập điểm vẽ `ploty` hoặc lưới điểm chia dày (dense check) thay vì chỉ kiểm tra 2 đầu mút `y = 0` và `y = h - 1`.
- Không làm giảm hiệu suất xử lý (FPS) của luồng video thời gian thực.
- Cắt giảm chiều cao vùng nhận diện (ROI) ở phía trên xuống khoảng một nửa (giới hạn từ 75% - 76% chiều cao khung hình trở xuống) để loại bỏ hoàn toàn nhiễu từ khung vòm thép và lan can của các cầu.
- Hệ thống phải tự động phát hiện và đảo ngược (swap) lại vạch kẻ đường nếu vạch trái và vạch phải bị nhận diện ngược bên nhau ở đáy ảnh.
- Thuật toán cửa sổ trượt phải có ràng buộc dịch chuyển ngang tối đa giữa các bước liên tiếp để tránh việc cửa sổ nhảy sang làn đối diện do nhiễu đốm sáng hoặc bóng xe.
- Các vạch kẻ đường vẽ trên màn hình HUD phải được vẽ dưới dạng đường cong mượt (cv2.polylines) khớp chính xác với biên của vùng di chuyển an toàn (Drivable Area) thay vì vẽ các đoạn thẳng thô nối hai đầu mút làm lệch hiển thị.

## 6. Service bị ảnh hưởng
- `lane-service`
