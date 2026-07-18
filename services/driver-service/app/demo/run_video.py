from __future__ import annotations

import cv2

from app.config import EYE_MODEL, MOUTH_MODEL
from app.demo.video_picker import pick_video
from app.services.drowsiness_detector import DrowsinessDetector


def main():

    video_path = pick_video()

    if video_path is None:
        print("Không chọn video.")
        return

    detector = DrowsinessDetector(
        eye_model_path=EYE_MODEL,
        mouth_model_path=MOUTH_MODEL,
    )

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print("Không mở được video.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30

    frame_index = 0
    paused = False

    try:
        while True:

            if not paused:

                ret, frame = cap.read()

                if not ret:
                    print("Hết video.")
                    break

                # QUAN TRỌNG: dùng timestamp theo TIMELINE CỦA VIDEO
                # (frame_index / fps), không phải đồng hồ hệ thống.
                # Nếu không, PERCLOS/microsleep/yawn-filter sẽ tính sai
                # khi tốc độ xử lý (CNN inference) không khớp tốc độ
                # phát thực của video (video xử lý chậm/nhanh hơn thực tế).
                timestamp = frame_index / fps

                frame, result = detector.process(frame, timestamp=timestamp)

                frame_index += 1

                # Log ra console để dễ theo dõi khi review lại video offline
                level = result["level"]
                if level.value != "NORMAL":
                    print(f"[t={timestamp:6.2f}s] level={level.value}")

            cv2.imshow("Driver Drowsiness Detection", frame)

            key = cv2.waitKey(int(1000 / fps)) & 0xFF

            if key == 27 or key == ord("q"):
                break

            # Space: tạm dừng / tiếp tục, hữu ích khi review video để xem
            # kỹ lúc nào model detect sai
            if key == ord(" "):
                paused = not paused

    finally:
        cap.release()
        cv2.destroyAllWindows()
        # Đóng detector nếu có phương thức close() (giải phóng MediaPipe)
        if hasattr(detector, "landmarker") and hasattr(detector.landmarker, "close"):
            detector.landmarker.close()


if __name__ == "__main__":
    main()