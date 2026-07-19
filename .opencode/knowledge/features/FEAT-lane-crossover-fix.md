# FEAT-lane-crossover-fix: Bộ lọc chống giao cắt làn đường (Crossover Protection) cho Geometry

## Thuộc Requirement
- [REQ-lane-crossover-fix](file:///h:/Web-python/multimodal-adas/.opencode/knowledge/requirements/REQ-lane-crossover-fix.md)

## Service
- `lane-service`

## Mô tả chức năng
- **Đầu vào**: Các hệ số đa thức bậc 2 được fit bởi Sliding Window trong lớp `LaneGeometry`.
- **Chức năng**:
  - Tính toán và so sánh tọa độ X của làn trái và phải tại các điểm chia trên trục Y trong không gian warped (bird's-eye view).
  - So sánh chi tiết trên toàn bộ khoảng đánh giá `[0, h - 1]`.
  - Nếu tồn tại vị trí mà vạch trái lấn sang bên phải vạch phải ($x_{left} \ge x_{right}$), đánh dấu là có sự giao cắt (Crossover anomaly).
  - Thực hiện fallback về EMA history hoặc trả về `None` cho tọa độ vẽ làn.
- **Đầu ra**: Tập hợp tọa độ vẽ làn đường ổn định không bị chéo.

## Acceptance Criteria
- Khi chạy trên camera thực tế hoặc video test, không xuất hiện hình chữ X màu xanh dương và đỏ cắt nhau.
- Nếu xảy ra nhiễu làm chéo đường, hệ thống không vẽ đường chéo đó mà giữ nguyên hiển thị cũ hoặc tắt đường biên vẽ, giữ HUD thông số an toàn.

## Độ ưu tiên
- **P0**: Ảnh hưởng trực tiếp đến chất lượng hiển thị và độ tin cậy của cảnh báo chệch làn.

## Phụ thuộc
- Không có phụ thuộc ngoài.
