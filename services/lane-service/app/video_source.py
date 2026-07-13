import cv2
import numpy as np
import requests



class VideoSource:
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.capture = cv2.VideoCapture(video_path)

        if not self.capture.isOpened():
            raise ValueError("Cannot open video file. Please check the uploaded video.")

    def get_info(self) -> dict:
        fps = float(self.capture.get(cv2.CAP_PROP_FPS))
        total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        duration_seconds = 0.0

        if fps > 0:
            duration_seconds = total_frames / fps

        return {
            "fps": round(fps, 2),
            "total_frames": total_frames,
            "width": width,
            "height": height,
            "duration_seconds": round(duration_seconds, 2),
        }

    def read_frames(self, max_frames: int = 30):
        frames_read = 0

        while frames_read < max_frames:
            success, frame = self.capture.read()

            if not success:
                break

            frames_read += 1
            yield frame

    def close(self) -> None:
        self.capture.release()


class HttpCameraSource:
    def __init__(self, url: str):
        self.url = url

    def get_info(self) -> dict:
        # Return default metadata for live stream
        return {
            "fps": 30.0,
            "total_frames": 0,
            "width": 640,
            "height": 480,
            "duration_seconds": 0.0,
        }

    def read_frames(self, max_frames: int = 999999):
        frames_read = 0
        while frames_read < max_frames:
            try:
                response = requests.get(self.url, timeout=1.0)
                if response.status_code == 200:
                    nparr = np.frombuffer(response.content, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        yield frame
                        frames_read += 1
                else:
                    break
            except Exception:
                # Wait briefly if connection is lost
                import time
                time.sleep(0.1)
                continue

    def close(self) -> None:
        pass