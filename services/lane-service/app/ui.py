import gradio as gr
import os

def create_gradio_app(analyze_video_file_func):
    def process(video_path):
        import traceback
        try:
            if not video_path:
                return {"error": "No video provided"}
            
            # Gradio 4.x sometimes passes a dict for video input depending on the exact component version
            if isinstance(video_path, dict):
                video_path = video_path.get("video", video_path)
                
            filename = os.path.basename(str(video_path))
            
            result = analyze_video_file_func(
                video_path=str(video_path),
                filename=filename,
                max_frames=30
            )
            return result
        except Exception as e:
            print("UI Process Error:", traceback.format_exc())
            return {
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    with gr.Blocks(title="Lane Service UI") as app:
        gr.Markdown("# Lane Detection Service - Test UI")
        gr.Markdown("Upload a video to test the Lane Service pipeline.")
        
        with gr.Row():
            with gr.Column():
                video_input = gr.Video(label="Input Video", sources=["upload"])
                analyze_btn = gr.Button("Analyze", variant="primary")
                
            with gr.Column():
                result_output = gr.JSON(label="Analysis Result")
                
        analyze_btn.click(
            fn=process,
            inputs=[video_input],
            outputs=[result_output]
        )
        
    return app
