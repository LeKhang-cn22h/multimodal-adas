# Session 2026-07-19 — Khắc phục lỗi giao cắt (X-Crossing) và Nhiễu vòm lan can cầu của lane-service

## Đã làm
- Phân tích và tạo hồ sơ Requirement: [REQ-lane-crossover-fix](file:///h:/Web-python/multimodal-adas/.opencode/knowledge/requirements/REQ-lane-crossover-fix.md) (Cập nhật đồng bộ hóa hiển thị và tinh chỉnh ROI 0.62).
- Phân tích và tạo đặc tả Feature: [FEAT-lane-crossover-fix](file:///h:/Web-python/multimodal-adas/.opencode/knowledge/features/FEAT-lane-crossover-fix.md) (Cập nhật trực quan hóa polylines đồng bộ Drivable Area).
- Xây dựng giải pháp kỹ thuật kiểm tra giao điểm dày (20 điểm) và hạn chế ROI: [TS-lane-crossover-fix](file:///h:/Web-python/multimodal-adas/.opencode/knowledge/tech-solutions/TS-lane-crossover-fix.md) (Đã xác nhận).
- Chỉnh sửa code thuật toán trong:
  - [geometry.py](file:///h:/Web-python/multimodal-adas/services/lane-service/app/core/geometry.py):
    - Cập nhật hàm `_sliding_window` để quét lưới Y dày 20 điểm nhằm phát hiện giao điểm.
    - Cập nhật hàm `analyze_lane` thêm lớp phòng vệ từ chối vẽ khi chéo làn, đồng thời trả thêm các hệ số `left_fitx`, `right_fitx`, `ploty`.
    - Tinh chỉnh tỷ lệ Y cao nhất của ROI (`src_pts` và `draw_lane_overlay`) lên mức **`0.62`** (giúp nhìn thấy vạch kẻ đứt để nhận diện ổn định, nhưng vẫn nằm hoàn toàn dưới gầm cầu và vòm thép ở `0.58` - `0.55`).
    - Hạn chế dịch chuyển của tâm cửa sổ trượt tối đa là `max_shift = int(w * 0.08)` so với cửa sổ trước đó.
    - Đáy vạch tự động đảo ngược (swap) nếu phát hiện bị nhầm bên.
  - [deeplab_segmenter.py](file:///h:/Web-python/multimodal-adas/services/lane-service/app/core/deeplab_segmenter.py):
    - Tinh chỉnh điểm đỉnh của hình thang `roi_pts` lên `0.62 * height`, đồng thời thu hẹp hai bên đáy (`0.18` và `0.82`) và đỉnh (`0.43` và `0.57`) để tránh nhiễu hộ lan/xe bên cạnh.
  - [pipeline.py](file:///h:/Web-python/multimodal-adas/services/lane-service/app/pipeline.py):
    - Thay thế cách vẽ đường thẳng thô bằng vẽ đường cong mượt `cv2.polylines` bằng cách dùng hàm chiếu ngược coordinates `_warp_point_inv`. Bản vẽ vạch đỏ/xanh dương giờ đây khớp 100% với biên của vùng di chuyển màu xanh lá.
- Tạo và chạy thành công script kiểm thử độc lập [verify_geometry.py](file:///C:/Users/Dell/.gemini/antigravity/brain/7e5e35c9-0ece-47d6-9729-20e28c3cf33f/scratch/verify_geometry.py) để xác thực logic thuật toán hoạt động chính xác.

## Quyết định quan trọng
- Tinh chỉnh ROI lên mức `0.62` để cân bằng hoàn hảo giữa khả năng nhìn thấy các vạch kẻ đường đứt đoạn phía trước (không bị mất vạch kẻ) và khả năng bỏ qua hoàn toàn nhiễu từ kết cấu dầm thép của cầu.
- Đồng bộ hóa bản vẽ vạch kẻ và vùng di chuyển bằng cách vẽ đường cong đa tuyến thay vì đường thẳng thô.

## Câu hỏi còn mở
- Không có.

## Việc tiếp theo
- Đẩy code chỉnh sửa và các tài liệu đặc tả mới lên nhánh `dev` của repository.
