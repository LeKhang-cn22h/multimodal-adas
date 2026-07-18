# ui.py
import gradio as gr

def ui_layout(update_fn):
    with gr.Blocks(title="Driver Safety Interface Gateway") as dashboard:
        gr.Markdown("## Hệ thống Giám sát Lái xe An toàn")
        
        with gr.Row():
            video_front = gr.Video(label="Camera Hành Trình (Front View)", format="mp4")
            video_driver = gr.Video(label="Camera Giám Sát Lái Xe (Driver View)", format="mp4")
            
        with gr.Row():
            signal_logs = gr.Textbox(label="Tín Hiệu Nhận Tới (Incoming Signals)", lines=10, interactive=False)
            safety_status = gr.Label(value="AN TOÀN", label="Trạng Thái Hiện Tại")
            
        with gr.Row():
            system_health = gr.Textbox(label="HỆ THỐNG", value="Hoạt động")
        ui_timer = gr.Timer(0.5)
        ui_timer.tick(
            fn=update_fn,
            inputs=None,
            outputs=[video_front, video_driver, signal_logs, safety_status, system_health]
        )
            
    # Return the main layout AND all components that need updating
    return dashboard