import os
import traceback
import gradio as gr

def create_gradio_app(analyze_video_file_func):
    """Tạo Gradio app để nhúng vào FastAPI."""
    def process(video_path):
        try:
            if not video_path:
                return {"error": "No video provided."}, "Chưa nhận diện", "UNKNOWN", "Chưa nhận diện"
            
            if isinstance(video_path, dict):
                video_path = video_path.get("video") or video_path.get("name", "")
                
            video_path = str(video_path)
            
            if not os.path.exists(video_path):
                return {"error": f"File not found: {video_path}"}, "Chưa nhận diện", "UNKNOWN", "Chưa nhận diện"
                
            filename = os.path.basename(video_path)
            result = analyze_video_file_func(
                video_path=video_path,
                filename=filename,
                max_frames=30
            )
            
            # Trích xuất thông tin
            last_frame = result.get("last_frame_result", {})
            offset = last_frame.get("lane_offset")
            direction = last_frame.get("direction", "UNKNOWN")
            num_dets = last_frame.get("num_detections", 0)
            
            offset_str = f"{offset} m" if offset is not None else "Chưa nhận diện"
            
            # Đổi nhãn trạng thái cảnh báo (Không dùng icon/emoji)
            if direction in ["LEFT", "RIGHT"]:
                direction_str = f"CANH BAO CHECH LAN ({direction})"
            else:
                direction_str = f"AN TOAN ({direction})"
                
            targets_str = f"Co {num_dets} phuong tien phia truoc"
            
            return result, offset_str, direction_str, targets_str
        except Exception as e:
            print("[ui] Error:", traceback.format_exc())
            return {"error": str(e)}, "Loi xu ly", "ERROR", "Chua nhan dien"

    # Custom CSS mang giao diện xanh Navy đậm kiểu TOC Dashboard
    custom_css = """
    .gradio-container {
        background-color: #0b1329 !important;
        color: #e2e8f0 !important;
        font-family: 'Inter', sans-serif !important;
    }
    /* Thẻ chứa card */
    .toc-card {
        background-color: #111e38 !important;
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        padding: 15px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    }
    .toc-title {
        color: #38bdf8 !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        margin-bottom: 12px !important;
        border-left: 4px solid #38bdf8;
        padding-left: 8px;
        line-height: 1.2;
    }
    /* Tùy chỉnh input/output text của Gradio */
    .gradio-container input, .gradio-container textarea, .gradio-container select {
        background-color: #1a294d !important;
        color: #ffffff !important;
        border: 1px solid #1e293b !important;
    }
    .gradio-container label span {
        color: #94a3b8 !important;
    }
    """

    # Header Bar mô phỏng thanh điều hướng mẫu của TOC (Đã loại bỏ toàn bộ icon/emoji)
    header_html = """
    <div style='display: flex; justify-content: space-between; align-items: center; background: linear-gradient(135deg, #111e38, #0b1329); padding: 12px 24px; border-bottom: 2px solid #1e293b; border-radius: 8px; margin-bottom: 15px;'>
        <div style='display: flex; align-items: center; gap: 20px;'>
            <span style='font-size: 1.5rem; font-weight: bold; color: #38bdf8; display: flex; align-items: center; gap: 8px;'>
                MULTIMODAL-ADAS
            </span>
            <div style='display: flex; gap: 15px; color: #94a3b8;'>
                <span style='cursor: pointer; padding: 4px 8px;'>Tong quan</span>
                <span style='cursor: pointer; padding: 4px 8px; color: #38bdf8; border-bottom: 2px solid #38bdf8; font-weight: bold;'>Phan tich lan (Lane ADAS)</span>
                <span style='cursor: pointer; padding: 4px 8px;'>Trang thai tai xe (DMS)</span>
                <span style='cursor: pointer; padding: 4px 8px;'>Thong so xe</span>
            </div>
        </div>
        <div style='display: flex; align-items: center; gap: 15px; color: #94a3b8; font-size: 0.9rem;'>
            <span style='display: flex; align-items: center; gap: 4px;'>GPS Connected</span>
            <span style='display: flex; align-items: center; gap: 4px;'>GPU Active</span>
            <span style='display: flex; align-items: center; gap: 8px; background-color: #1e293b; padding: 6px 12px; border-radius: 20px; color: #fff;'>
                Tai xe: Ngoc Mai
            </span>
        </div>
    </div>
    """

    with gr.Blocks(title="MULTIMODAL-ADAS Dashboard", css=custom_css) as app:
        # Header
        gr.HTML(header_html)
        
        # Bố cục 3 cột chính
        with gr.Row():
            # CỘT TRÁI: Cảm biến & Lớp phủ (Sidebar)
            with gr.Column(scale=1, elem_classes="toc-card"):
                gr.HTML("<div class='toc-title'>CAM BIEN & LOP PHU</div>")
                
                # Danh mục camera nguồn
                gr.Markdown("**Chon Nguon Video / Camera**")
                camera_select = gr.Radio(
                    choices=["Camera truoc ADAS (Live)", "Camera phu"],
                    value="Camera truoc ADAS (Live)",
                    label="Camera Inputs",
                    show_label=False
                )
                
                gr.Markdown("---")
                
                # Các lớp phủ trực quan
                gr.Markdown("**Bat/Tat cac Lop phu (Overlay)**")
                overlay_lane = gr.Checkbox(label="Vach ke lan duong", value=True)
                overlay_yolo = gr.Checkbox(label="Vat can YOLOv11", value=True)
                overlay_drivable = gr.Checkbox(label="Vung di chuyen duoc", value=True)
                
                gr.Markdown("---")
                
                # Cấu hình tham số mô hình
                gr.Markdown("**Cau hinh Tham so AI**")
                conf_threshold = gr.Slider(minimum=0.1, maximum=1.0, value=0.35, label="Conf Threshold (YOLO)")
                limit_frames = gr.Slider(minimum=10, maximum=100, step=10, value=30, label="Gioi han phan tich (Frames)")
                
            # CỘT GIỮA: Màn hình Livestream chính & Khu vực Upload
            with gr.Column(scale=3):
                # Khung hiển thị Live Stream chính
                with gr.Column(elem_classes="toc-card"):
                    gr.HTML("<div class='toc-title'>MONITOR: CAMERA HANH TRINH PHIA TRUOC</div>")
                    # Nhúng mjpeg stream cung cấp từ endpoint /stream
                    gr.HTML(
                        "<div style='display: flex; justify-content: center; background-color: #060b13; padding: 10px; border-radius: 6px; border: 1px solid #1e293b;'>"
                        "  <img src='/stream' style='width: 100%; max-width: 640px; border-radius: 4px;'>"
                        "</div>"
                    )
                
                gr.Markdown("")
                
                # Khung upload file video thử nghiệm bên dưới
                with gr.Row(elem_classes="toc-card"):
                    with gr.Column():
                        gr.HTML("<div class='toc-title'>KIEM THU VIDEO KHAC</div>")
                        video_input = gr.Video(label="Tai len Video", sources=["upload"])
                        analyze_btn = gr.Button("Bat dau Phan tich", variant="primary")
                    with gr.Column():
                        gr.HTML("<div class='toc-title'>KET QUA PHAN HOI (JSON)</div>")
                        result_output = gr.JSON(label="JSON Result", show_label=False)

            # CỘT PHẢI: Thông tin Cảnh báo & Vận hành
            with gr.Column(scale=1, elem_classes="toc-card"):
                gr.HTML("<div class='toc-title'>THONG TIN CANH BAO ADAS</div>")
                
                # Trạng thái cảnh báo an toàn lái xe
                direction_output = gr.Textbox(
                    label="Trang thai chech lan", 
                    value="AN TOAN (CENTER)", 
                    interactive=False
                )
                
                # Độ lệch làn đường
                offset_output = gr.Textbox(
                    label="Do lech lan (Lane Offset)", 
                    value="0.0 m", 
                    interactive=False
                )
                
                # Số lượng xe/vật cản phát hiện
                targets_output = gr.Textbox(
                    label="Phuong tien phia truoc (YOLO)", 
                    value="Chua nhan dien", 
                    interactive=False
                )
                
                gr.Markdown("---")
                
                # Giám sát trạng thái tài xế (DMS Mockup)
                gr.HTML("<div class='toc-title'>GIAM SAT TAI XE (DMS)</div>")
                gr.Textbox(label="Trang thai mat/khuon mat", value="Tap trung (Tinh tao)", interactive=False)
                gr.Textbox(label="PERCLOS (Ty le nham mat)", value="An toan (0.08)", interactive=False)
                
                gr.Markdown("---")
                
                # Thông số vận hành giả lập khác của xe
                gr.HTML("<div class='toc-title'>THONG SO VAN HANH XE</div>")
                gr.Textbox(label="Van toc hien tai", value="80 km/h", interactive=False)
                gr.Textbox(label="Loa canh bao am thanh", value="DANG TAT", interactive=False)

        # Định nghĩa sự kiện nhấn nút phân tích video
        analyze_btn.click(
            fn=process,
            inputs=[video_input],
            outputs=[result_output, offset_output, direction_output, targets_output]
        )
        
    return app
