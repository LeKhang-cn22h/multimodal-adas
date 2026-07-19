# FEAT-lane-crossover-fix: Bộ lọc chống giao cắt làn đường (Crossover Protection) cho Geometry

## Thuộc Requirement
- [REQ-lane-crossover-fix](file:///h:/Web-python/multimodal-adas/.opencode/knowledge/requirements/REQ-lane-crossover-fix.md)

## Service
- `lane-service`

## Mô tả chức năng
- **Đầu vào**: Các hệ số đa thức bậc 2 được fit bởi Sliding Window trong lớp `LaneGeometry` và mask phân vùng ảnh đầu vào.
- **Chức năng**:
  - Tích hợp bộ lọc ROI giới hạn từ `0.76 * height` trở xuống (cắt bớt một nửa chiều cao quét từ trên xuống) để bỏ qua phần vòm cầu và lan can cầu.
  - Tính toán và so sánh tọa độ X của làn trái và phải tại các điểm chia trên trục Y trong không gian warped (bird's-eye view).
  - So sánh chi tiết trên toàn bộ khoảng đánh giá `[0, h - 1]`.
  - Nếu tồn tại vị trí mà vạch trái lấn sang bên phải vạch phải ($x_{left} \ge x_{right}$), đánh dấu là có sự giao cắt (Crossover anomaly).
  - Thực hiện fallback về EMA history hoặc trả về `None` cho tọa độ vẽ làn.
  - Tự động sửa lỗi nhầm vạch (swap vạch): Nếu tọa độ đáy vạch trái lớn hơn tọa độ đáy vạch phải, tự động đảo ngược hệ số của chúng về đúng vị trí.
  - Hạn chế bước dịch chuyển ngang (delta limit) của tâm cửa sổ trượt tối đa là 8% chiều rộng frame để tránh nhảy sang vạch làn bên cạnh.
  - Trực quan hóa vạch kẻ đường dạng đường cong (cv2.polylines) thay vì đường thẳng thô (cv2.line) để đảm bảo đồng bộ hoàn toàn với biên của vùng di chuyển an toàn (Drivable Area).
- **Đầu ra**: Tập hợp tọa độ vẽ làn đường dạng đường cong và vùng di chuyển ổn định không bị chéo, không bị ngược bên và đồng bộ hoàn hảo với nhau.

## Acceptance Criteria
- Khi chạy trên camera thực tế hoặc video test, không xuất hiện hình chữ X màu xanh dương và đỏ cắt nhau.
- Nếu xảy ra nhiễu làm chéo đường, hệ thống không vẽ đường chéo đó mà giữ nguyên hiển thị cũ hoặc tắt đường biên vẽ, giữ HUD thông số an toàn.

## Độ ưu tiên
- **P0**: Ảnh hưởng trực tiếp đến chất lượng hiển thị và độ tin cậy của cảnh báo chệch làn.

## Phụ thuộc
- Không có phụ thuộc ngoài.
