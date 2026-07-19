# TS-lane-crossover-fix: Giải pháp kiểm tra giao cắt làn đường dùng lưới quét dày

## Thuộc Feature
- [FEAT-lane-crossover-fix](file:///h:/Web-python/multimodal-adas/.opencode/knowledge/features/FEAT-lane-crossover-fix.md)

## Kiến trúc
Chỉnh sửa cấu trúc logic trong `services/lane-service/app/core/geometry.py` và `deeplab_segmenter.py`:
1. `LaneGeometry._sliding_window()`:
   - Sửa đổi từ việc kiểm tra chỉ tại 2 đầu mút (`0` và `h-1`) thành kiểm tra lưới điểm dọc (ví dụ: 20 điểm phân bố đều từ `0` đến `h-1`).
   - Nếu có giao cắt, kích hoạt fallback sử dụng EMA hoặc trả về `None`.
   - **Hạn chế dịch chuyển (Delta Limiting)**: Giới hạn dịch chuyển của tâm cửa sổ trượt tối đa là `max_shift = int(w * 0.08)` so với cửa sổ trước đó để loại bỏ hiện tượng nhảy vạch hoặc nhiễu.
   - **Tự động đảo ngược nhầm vạch (Auto-Swap)**: Kiểm tra ở đáy ảnh nếu `left_temp_x[-1] > right_temp_x[-1]`, tiến hành đảo ngược hệ số `lf` và `rf` để định hướng đúng vạch trái/phải.
2. `LaneGeometry.analyze_lane()`:
   - Thêm lớp phòng vệ phụ (Defense in Depth) kiểm tra kết quả `left_fitx` and `right_fitx` sau khi tính toán. Nếu vẫn phát hiện giao cắt, trả về `lane_detected: False` và `left_line: None`, `right_line: None` để bảo vệ hiển thị ở HUD gốc.
   - Trả thêm `left_fitx`, `right_fitx`, và `ploty` trong từ điển kết quả trả về để hỗ trợ vẽ đường cong mượt.
3. **Cắt giảm chiều cao ROI (Hạ đường chân trời nhận diện xuống 0.65 - khớp tỷ lệ 2/3)**:
   - Trong `geometry.py`: Thay đổi `src_pts` có tọa độ Y trên cùng từ `0.55` thành `0.65`. Đồng thời, chỉnh sửa `y_start = int(h * 0.65)` trong `draw_lane_overlay`.
   - Trong `deeplab_segmenter.py`: Sửa đổi tọa độ đỉnh của `roi_pts` từ `height * 0.52` thành `height * 0.65` (khớp chính xác với tỉ lệ 2/3 chiều cao của code tham khảo).
   - Tích hợp trực tiếp Canny Edge Mask: Thay thế `cv2.bitwise_and(canny_mask, dilated_hsv)` bằng sử dụng trực tiếp `canny_mask` thô để đảm bảo luôn có pixel vạch kẻ, tăng độ ổn định của đường trượt (Sliding Window) ngay cả khi HSV bị mất dấu do ánh sáng.
5. **Tích hợp chế độ Hough Transform truyền thống làm mặc định**:
   - Dịch vụ hỗ trợ chuyển đổi linh hoạt chế độ phát hiện làn qua tham số cấu hình `lane_mode` (mặc định đặt là `"hough"` theo chỉ thị trực tiếp từ người dùng).
   - Tích hợp lớp `HoughLaneDetector` trong `hough_lane.py` vào `pipeline.py`. Thiết lập ROI đỉnh cao `0.65` (khớp tỷ lệ 2/3), Canny `60, 255`, và giãn nở Morphological `3x3` đúng như code tham khảo.
   - Nhận diện các đoạn thẳng bằng `cv2.HoughLinesP`, tính toán trung bình có trọng số theo chiều dài đoạn và lọc dốc để tìm 2 vạch trái/phải.
   - Vẽ trực quan hóa vùng di chuyển bằng đa giác `cv2.fillPoly` giới hạn bởi 2 đường thẳng và vẽ biên bằng `cv2.line` (xanh dương cho trái, đỏ cho phải) với độ dày `4` sắc nét, đồng bộ.

## Logic + AI
- **Thuật toán**:
  - **Chế độ Geometry**:
    - Tạo lưới chia trục Y: `ploty_check = np.linspace(0, h - 1, 20)`
    - Tính tọa độ X tại các điểm lưới:
      $$x_{left} = a_{left} \cdot y^2 + b_{left} \cdot y + c_{left}$$
      $$x_{right} = a_{right} \cdot y^2 + b_{right} \cdot y + c_{right}$$
    - Điều kiện phát hiện giao cắt:
      $$\exists y \in \text{ploty\_check} \quad \text{sao cho} \quad x_{left}(y) \ge x_{right}(y)$$
      Biểu diễn bằng code: `np.any(left_temp_x >= right_temp_x)`
  - **Chế độ Hough**:
    - Canny Edge Map: `canny = cv2.Canny(dilated, 60, 255)`
    - Hough Transform: `cv2.HoughLinesP(roi_image, 1, np.pi/180, 40, minLineLength=10, maxLineGap=5)`
    - Phân tách vạch bằng slope (dốc âm là trái, dốc dương là phải) và lọc ngang.
- **Độ phức tạp**: Cực kỳ nhỏ ($O(1)$ với 20 phép nhân ma trận nhỏ hoặc các phép lọc tuyến tính của OpenCV), không ảnh hưởng đến FPS của hệ thống.

## API Contract
Không thay đổi API contract bên ngoài. Chỉ sửa đổi xử lý logic thuật toán nội bộ.

## Rủi ro & câu hỏi mở
Không có rủi ro lớn. Thuật toán hoạt động hoàn toàn trên RAM và không phụ thuộc bên ngoài.

## Ảnh hưởng tới service khác
Không ảnh hưởng đến các service khác.

## Trạng thái xác nhận
- [x] Đã xác nhận bởi người dùng ngày 2026-07-19 (qua chỉ thị trực tiếp chuyển đổi sang chế độ Hough Transform)
