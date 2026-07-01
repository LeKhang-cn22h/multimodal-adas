import os
import traceback
import shutil
import gradio as gr


def create_gradio_app(analyze_video_file_func, change_stream_func):
    """Tạo Gradio app để nhúng vào FastAPI."""

    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "test_videos")
    os.makedirs(base_dir, exist_ok=True)

    VIDEO_EXTS = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.wmv', '.flv')

    def get_video_choices():
        try:
            files = [f for f in os.listdir(base_dir) if f.lower().endswith(VIDEO_EXTS)]
            return sorted(files) if files else ["solidWhiteRight.mp4"]
        except Exception:
            return ["solidWhiteRight.mp4"]

    initial_choices = get_video_choices()

    # ---------------------------------------------------------------
    # Card renderers - trả về HTML để hiển thị dữ liệu trực quan hơn
    # thay vì các Textbox đơn sắc.
    # ---------------------------------------------------------------
    def render_stat_card(icon, label, value, color="#38bdf8", sub=None):
        sub_html = f"<div class='stat-sub'>{sub}</div>" if sub else ""
        icon_html = f"<div class='stat-icon'>{icon}</div>" if icon else ""
        return f"""
        <div class='stat-card' style='--accent:{color}'>
            {icon_html}
            <div class='stat-body'>
                <div class='stat-label'>{label}</div>
                <div class='stat-value'>{value}</div>
                {sub_html}
            </div>
        </div>
        """

    def render_direction_card(direction):
        if direction in ["LEFT", "RIGHT"]:
            return render_stat_card(
                None, "TRẠNG THÁI LÁI",
                f"CHỆCH LÀN ({direction})",
                color="#ef4444",
                sub="Cần điều chỉnh vô lăng ngay"
            )
        elif direction == "UNKNOWN":
            return render_stat_card(None, "TRẠNG THÁI LÁI", "CHƯA NHẬN DIỆN", color="#64748b")
        return render_stat_card(None, "TRẠNG THÁI LÁI", f"AN TOÀN ({direction})", color="#10b981")

    def render_offset_card(offset_str, offset_val=None):
        color = "#10b981"
        sub = None
        if offset_val is not None:
            try:
                if abs(float(offset_val)) > 0.5:
                    color = "#f59e0b"
                    sub = "Lệch tâm làn đáng chú ý"
            except (TypeError, ValueError):
                pass
        return render_stat_card(None, "ĐỘ LỆCH LÀN", offset_str, color=color, sub=sub)

    def render_targets_card(num_dets, targets_str):
        color = "#38bdf8" if num_dets else "#64748b"
        return render_stat_card(None, "VẬT CẢN PHÍA TRƯỚC", targets_str, color=color)

    IDLE_DIRECTION = render_stat_card(None, "TRẠNG THÁI LÁI", "CHƯA NHẬN DIỆN", color="#64748b")
    IDLE_OFFSET = render_stat_card(None, "ĐỘ LỆCH LÀN", "Chưa nhận diện", color="#64748b")
    IDLE_TARGETS = render_stat_card(None, "VẬT CẢN PHÍA TRƯỚC", "Chưa nhận diện", color="#64748b")

    def process(video_path):
        try:
            if not video_path:
                return {"error": "No video provided."}, IDLE_OFFSET, IDLE_DIRECTION, IDLE_TARGETS, gr.update()

            if isinstance(video_path, dict):
                video_path = video_path.get("video") or video_path.get("name", "")

            video_path = str(video_path)

            if not os.path.exists(video_path):
                err_card = render_stat_card(None, "LỖI", f"Không tìm thấy file: {video_path}", color="#ef4444")
                return {"error": f"File not found: {video_path}"}, IDLE_OFFSET, err_card, IDLE_TARGETS, gr.update()

            filename = os.path.basename(video_path)
            save_path = os.path.join(base_dir, filename)

            if os.path.abspath(video_path) != os.path.abspath(save_path):
                shutil.copy2(video_path, save_path)

            result = analyze_video_file_func(
                video_path=save_path,
                filename=filename,
                max_frames=30
            )

            last_frame = result.get("last_frame_result", {})
            offset = last_frame.get("lane_offset")
            direction = last_frame.get("direction", "UNKNOWN")
            num_dets = last_frame.get("num_detections", 0)

            offset_str = f"{offset} m" if offset is not None else "Chưa nhận diện"
            targets_str = f"{num_dets} phương tiện" if num_dets else "Không phát hiện"

            updated_choices = get_video_choices()

            return (
                result,
                render_offset_card(offset_str, offset),
                render_direction_card(direction),
                render_targets_card(num_dets, targets_str),
                gr.update(choices=updated_choices, value=filename),
            )
        except Exception as e:
            print("[ui] Error:", traceback.format_exc())
            err_card = render_stat_card(None, "LỖI XỬ LÝ", str(e), color="#ef4444")
            return {"error": str(e)}, IDLE_OFFSET, err_card, IDLE_TARGETS, gr.update()

    def on_camera_change(selected_video):
        if not selected_video:
            return gr.update()
        full_path = os.path.join(base_dir, selected_video)
        if os.path.exists(full_path):
            change_stream_func(full_path)
            return f"Đang phát: **{selected_video}**"
        return f"Không tìm thấy video: **{selected_video}**"

    def on_browse_file(file_path):
        """Xử lý khi người dùng bấm nút 'Chọn file bất kỳ' và chọn 1 video
        từ máy của họ (không giới hạn trong danh sách có sẵn)."""
        try:
            if not file_path:
                return gr.update(), gr.update()

            file_path = str(file_path)
            if not os.path.exists(file_path):
                return gr.update(), "Không tìm thấy file đã chọn"

            filename = os.path.basename(file_path)
            if not filename.lower().endswith(VIDEO_EXTS):
                return gr.update(), f"Định dạng không hỗ trợ: {filename}"

            save_path = os.path.join(base_dir, filename)
            if os.path.abspath(file_path) != os.path.abspath(save_path):
                shutil.copy2(file_path, save_path)

            # Phát ngay video vừa chọn lên màn hình giám sát
            change_stream_func(save_path)

            updated_choices = get_video_choices()
            return (
                gr.update(choices=updated_choices, value=filename),
                f"Đang phát: **{filename}**",
            )
        except Exception as e:
            print("[ui] Browse error:", traceback.format_exc())
            return gr.update(), f"Lỗi khi mở file: {e}"

    def on_upload_start():
        return "Đang phân tích video, vui lòng chờ..."

    def on_process_done(video_path):
        if video_path:
            filename = os.path.basename(str(video_path))
            return f"Đang phát: **{filename}**"
        return gr.update()

    # ---------------------------------------------------------------
    # CSS
    # ---------------------------------------------------------------
    custom_css = """
    .gradio-container {
        background: radial-gradient(circle at top left, #101c3a 0%, #0b1329 55%, #070c1a 100%) !important;
        color: #e2e8f0 !important;
        font-family: 'Inter', system-ui, sans-serif !important;
    }

    .toc-card {
        background-color: #111e38 !important;
        border: 1px solid #1e2b4d !important;
        border-radius: 14px !important;
        padding: 16px !important;
        box-shadow: 0 8px 20px -8px rgba(0, 0, 0, 0.45) !important;
    }

    .toc-title {
        color: #38bdf8 !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-bottom: 14px !important;
        border-left: 4px solid #38bdf8;
        padding-left: 10px;
        line-height: 1.3;
    }

    .gradio-container input, .gradio-container textarea, .gradio-container select {
        background-color: #17233f !important;
        color: #ffffff !important;
        border: 1px solid #223055 !important;
        border-radius: 8px !important;
    }

    .gradio-container label span { color: #94a3b8 !important; }

    /* Stat card layout */
    .stat-card {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        background: linear-gradient(135deg, #16223f, #101a33);
        border: 1px solid #223055;
        border-left: 4px solid var(--accent, #38bdf8);
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px -6px rgba(0,0,0,0.5);
    }
    .stat-icon {
        font-size: 1.6rem;
        line-height: 1;
        filter: drop-shadow(0 0 6px rgba(56,189,248,0.25));
    }
    .stat-body { flex: 1; }
    .stat-label {
        font-size: 0.72rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
    }
    .stat-value {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .stat-sub {
        font-size: 0.75rem;
        color: #cbd5e1;
        margin-top: 3px;
        opacity: 0.85;
    }

    .stream-frame {
        display: flex;
        justify-content: center;
        background-color: #05080f;
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #223055;
    }
    .stream-frame img {
        width: 100%;
        max-width: 680px;
        border-radius: 6px;
    }

    #analyze_btn, #browse_btn {
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    #browse_btn {
        margin-top: 8px !important;
    }
    """

    header_html = """
    <div style='display: flex; justify-content: space-between; align-items: center;
                background: linear-gradient(135deg, #142042, #0b1329);
                padding: 14px 26px; border-bottom: 2px solid #1e293b; border-radius: 12px; margin-bottom: 16px;
                box-shadow: 0 6px 18px -8px rgba(0,0,0,0.5);'>
        <div style='display: flex; align-items: center; gap: 14px;'>
            <span style='font-size: 1.4rem; font-weight: 800; color: #38bdf8; letter-spacing: 0.02em;'>
                MULTIMODAL-ADAS Dashboard
            </span>
        </div>
        <div style='display: flex; align-items: center; gap: 18px; color: #94a3b8; font-size: 0.85rem;'>
            <span>GPS Connected</span>
            <span style='color: #10b981; font-weight: 600;'>● GPU Active</span>
        </div>
    </div>
    """

    default_val = initial_choices[0] if initial_choices else "solidWhiteRight.mp4"

    with gr.Blocks(title="MULTIMODAL-ADAS Dashboard", css=custom_css) as app:
        gr.HTML(header_html)

        with gr.Row():
            # CỘT TRÁI: Chọn nguồn phát
            with gr.Column(scale=1, elem_classes="toc-card"):
                gr.HTML("<div class='toc-title'>Nguồn video camera</div>")

                camera_select = gr.Dropdown(
                    choices=initial_choices,
                    value=default_val,
                    label="Video đã lưu",
                    show_label=True,
                )

                browse_btn = gr.UploadButton(
                    "Chọn file bất kỳ...",
                    file_types=["video"],
                    file_count="single",
                    variant="secondary",
                    elem_id="browse_btn",
                )

                cam_status = gr.Markdown(f"Đang phát: **{default_val}**")

            # CỘT GIỮA: Livestream & Upload
            with gr.Column(scale=3):
                with gr.Column(elem_classes="toc-card"):
                    gr.HTML("<div class='toc-title'>Màn hình giám sát ADAS</div>")
                    gr.HTML(
                        "<div class='stream-frame'>"
                        "  <img src='/stream'>"
                        "</div>"
                    )

                with gr.Column(elem_classes="toc-card"):
                    gr.HTML("<div class='toc-title'>Tải lên video kiểm thử</div>")
                    video_input = gr.Video(label="Upload Video", sources=["upload"])
                    analyze_btn = gr.Button("Phân tích và phát Live", variant="primary", elem_id="analyze_btn")

            # CỘT PHẢI: Thông số ADAS & JSON
            with gr.Column(scale=1, elem_classes="toc-card"):
                gr.HTML("<div class='toc-title'>Thông số ADAS thực tế</div>")

                direction_output = gr.HTML(IDLE_DIRECTION)
                offset_output = gr.HTML(IDLE_OFFSET)
                targets_output = gr.HTML(IDLE_TARGETS)

                with gr.Accordion("Kết quả phản hồi (JSON)", open=False):
                    result_output = gr.JSON(label="JSON Result", show_label=False)

        # Đổi nguồn stream khi chọn 1 video có sẵn trong dropdown
        camera_select.change(
            fn=on_camera_change,
            inputs=[camera_select],
            outputs=[cam_status]
        )

        # Bấm nút "Chọn file bất kỳ" -> mở trình duyệt file của hệ thống,
        # chọn video bất kỳ (không giới hạn trong danh sách có sẵn) và phát ngay
        browse_btn.upload(
            fn=on_browse_file,
            inputs=[browse_btn],
            outputs=[camera_select, cam_status]
        )

        # Phân tích video khi bấm nút
        analyze_btn.click(
            fn=on_upload_start,
            inputs=None,
            outputs=[cam_status]
        ).then(
            fn=process,
            inputs=[video_input],
            outputs=[result_output, offset_output, direction_output, targets_output, camera_select]
        ).then(
            fn=on_process_done,
            inputs=[video_input],
            outputs=[cam_status]
        )

    return app