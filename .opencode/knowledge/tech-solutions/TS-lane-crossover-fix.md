# TS-lane-crossover-fix: Giải pháp kiểm tra giao cắt làn đường dùng lưới quét dày

## Thuộc Feature
- [FEAT-lane-crossover-fix](file:///h:/Web-python/multimodal-adas/.opencode/knowledge/features/FEAT-lane-crossover-fix.md)

## Kiến trúc
Chỉnh sửa cấu trúc logic trong `services/lane-service/app/core/geometry.py` và `deeplab_segmenter.py`:
1. `LaneGeometry._sliding_window()`:
   - Sửa đổi từ việc kiểm tra chỉ tại 2 đầu mút (`0` và `h-1`) thành kiểm tra lưới điểm dọc (ví dụ: 20 điểm phân bố đều từ `0` đến `h-1`).
   - Nếu có giao cắt, kích hoạt fallback sử dụng EMA hoặc trả về `None`.
2. `LaneGeometry.analyze_lane()`:
   - Thêm lớp phòng vệ phụ (Defense in Depth) kiểm tra kết quả `left_fitx` and `right_fitx` sau khi tính toán. Nếu vẫn phát hiện giao cắt, trả về `lane_detected: False` và `left_line: None`, `right_line: None` để bảo vệ hiển thị ở HUD gốc.
3. **Cắt giảm chiều cao ROI (Hạ đường chân trời nhận diện xuống 0.76)**:
   - Trong `geometry.py`: Thay đổi `src_pts` có tọa độ Y trên cùng từ `0.55` thành `0.76`. Đồng thời, chỉnh sửa `y_start = int(h * 0.76)` trong `draw_lane_overlay`.
   - Trong `deeplab_segmenter.py`: Sửa đổi tọa độ đỉnh của `roi_pts` từ `height * 0.52` thành `height * 0.76`. Điều này sẽ cắt bỏ hoàn toàn một nửa vùng quét phía trên, bỏ qua vòm thép cầu.

## Logic + AI
- **Thuật toán**:
  - Tạo lưới chia trục Y: `ploty_check = np.linspace(0, h - 1, 20)`
  - Tính tọa độ X tại các điểm lưới:
    $$x_{left} = a_{left} \cdot y^2 + b_{left} \cdot y + c_{left}$$
    $$x_{right} = a_{right} \cdot y^2 + b_{right} \cdot y + c_{right}$$
  - Điều kiện phát hiện giao cắt:
    $$\exists y \in \text{ploty\_check} \quad \text{sao cho} \quad x_{left}(y) \ge x_{right}(y)$$
    Biểu diễn bằng code: `np.any(left_temp_x >= right_temp_x)`
- **Độ phức tạp**: Cực kỳ nhỏ ($O(1)$ với 20 phép nhân ma trận nhỏ), không ảnh hưởng đến FPS của hệ thống.

## API Contract
Không thay đổi API contract bên ngoài. Chỉ sửa đổi xử lý logic thuật toán nội bộ.

## Rủi ro & câu hỏi mở
Không có rủi ro lớn. Thuật toán hoạt động hoàn toàn trên RAM và không phụ thuộc bên ngoài.

## Ảnh hưởng tới service khác
Không ảnh hưởng đến các service khác.

## Trạng thái xác nhận
- [x] Đã xác nhận bởi người dùng ngày 2026-07-19 (qua chỉ thị trực tiếp)
