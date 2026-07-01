import os
import traceback
import gradio as gr

def create_gradio_app(analyze_video_file_func):
    """Tạo Gradio app để nhúng vào FastAPI."""
    def process(video_path):
        try:
            if not video_path:
                return {"error": "No video provided. Please upload a file."}, "Not Detected", "UNKNOWN"
            
            if isinstance(video_path, dict):
                video_path = video_path.get("video") or video_path.get("name", "")
                
            video_path = str(video_path)
            
            if not os.path.exists(video_path):
                return {"error": f"File not found: {video_path}"}, "Not Detected", "UNKNOWN"
                
            filename = os.path.basename(video_path)
            result = analyze_video_file_func(
                video_path=video_path,
                filename=filename,
                max_frames=30
            )
            
            # Trích xuất thông số lái xe động từ frame cuối cùng được xử lý
            last_frame = result.get("last_frame_result", {})
            offset = last_frame.get("lane_offset")
            direction = last_frame.get("direction", "UNKNOWN")
            
            offset_str = f"{offset} m" if offset is not None else "Chưa nhận diện"
            
            # Bổ sung cảnh báo nếu chệch làn
            if direction in ["LEFT", "RIGHT"]:
                direction_str = f"⚠️ CHỆCH LÀN ({direction})"
            else:
                direction_str = f"✅ AN TOÀN ({direction})"
                
            return result, offset_str, direction_str
        except Exception as e:
            print("[ui] Error:", traceback.format_exc())
            return {"error": str(e), "traceback": traceback.format_exc()}, "Lỗi xử lý", "ERROR"

    with gr.Blocks(title="Lane & Object Detection Service") as app:
        gr.Markdown("# 🛣️ Lane & Object Detection Service")
        
        # Phần Livestream trực quan (kết hợp hướng A và B)
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 🎥 Live Stream Pipeline (YOLOv11 BBox + Lane Alpha Overlay)")
                gr.HTML(
                    "<div style='display: flex; justify-content: center; background-color: #1e1e1e; padding: 10px; border-radius: 8px;'>"
                    "  <img src='/stream' style='width: 100%; max-width: 640px; border-radius: 4px; border: 1px solid #333;'>"
                    "</div>"
                )
        
        # Phần Upload Video thủ công để lấy dữ liệu JSON và thông số lái
        gr.Markdown("---")
        gr.Markdown("### 📥 Test Manual Video (Upload & Get JSON Data)")
        with gr.Row():
            with gr.Column():
                video_input = gr.Video(label="Input Video", sources=["upload"])
                analyze_btn = gr.Button("Analyze", variant="primary")
                
            with gr.Column():
                with gr.Row():
                    offset_output = gr.Textbox(label="Độ lệch làn (Lane Offset)", interactive=False)
                    direction_output = gr.Textbox(label="Trạng thái lái (Status)", interactive=False)
                result_output = gr.JSON(label="Analysis Result")
                
        analyze_btn.click(
            fn=process,
            inputs=[video_input],
            outputs=[result_output, offset_output, direction_output]
        )
        
    return app
