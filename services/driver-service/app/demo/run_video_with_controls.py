from __future__ import annotations

import cv2

from app.config import EYE_MODEL, MOUTH_MODEL, SEATBELT_MODEL
from app.core.app_runtime_config import AppRuntimeConfig
from app.demo.video_picker import pick_video
from app.services.drowsiness_detector import DrowsinessDetector
from app.services.safety_monitor import SafetyMonitor
from app.services.seatbelt_detector import SeatbeltDetector

WINDOW_NAME = "Driver Safety Monitor"
CONTROL_WINDOW = "Controls"


def setup_controls(runtime_config: AppRuntimeConfig) -> None:
    """Tạo cửa sổ trackbar để bật/tắt model và chỉnh tần suất lúc chạy."""

    cv2.namedWindow(CONTROL_WINDOW)

    cv2.createTrackbar(
        "Drowsiness ON/OFF", CONTROL_WINDOW,
        1 if runtime_config.drowsiness_enabled else 0, 1,
        lambda v: setattr(runtime_config, "drowsiness_enabled", bool(v)),
    )

    cv2.createTrackbar(
        "Seatbelt ON/OFF", CONTROL_WINDOW,
        1 if runtime_config.seatbelt_enabled else 0, 1,
        lambda v: setattr(runtime_config, "seatbelt_enabled", bool(v)),
    )

    cv2.createTrackbar(
        "Seatbelt: check moi N frame", CONTROL_WINDOW,
        runtime_config.seatbelt_check_every_n_frames, 60,
        lambda v: setattr(runtime_config, "seatbelt_check_every_n_frames", max(1, v)),
    )


def main():

    video_path = pick_video()

    if video_path is None:
        print("Không chọn video.")
        return

    runtime_config = AppRuntimeConfig(
        drowsiness_enabled=True,
        seatbelt_enabled=True,
        seatbelt_check_every_n_frames=10,
    )

    drowsiness_detector = DrowsinessDetector(
        eye_model_path=EYE_MODEL,
        mouth_model_path=MOUTH_MODEL,
    )

    seatbelt_detector = SeatbeltDetector(
        model_path=SEATBELT_MODEL,
    )

    monitor = SafetyMonitor(
        drowsiness_detector=drowsiness_detector,
        seatbelt_detector=seatbelt_detector,
        runtime_config=runtime_config,
    )

    setup_controls(runtime_config)

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print("Không mở được video.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30

    frame_index = 0
    paused = False
    frame = None

    try:
        while True:

            if not paused:

                ret, frame = cap.read()

                if not ret:
                    print("Hết video.")
                    break

                # Dùng timestamp theo TIMELINE CỦA VIDEO (frame_index / fps),
                # không phải đồng hồ hệ thống — để PERCLOS/microsleep/yawn-filter
                # tính đúng theo thời lượng video, không phụ thuộc tốc độ xử lý
                # thực tế (CNN + YOLO có thể chạy chậm hơn/nhanh hơn tốc độ phát).
                timestamp = frame_index / fps

                frame, result = monitor.process(frame, timestamp=timestamp)

                frame_index += 1

                drowsiness_result = result.get("drowsiness")
                if drowsiness_result and drowsiness_result["level"].value != "NORMAL":
                    print(f"[t={timestamp:6.2f}s] drowsiness={drowsiness_result['level'].value}")

                seatbelt_result = result.get("seatbelt")
                if seatbelt_result and seatbelt_result.get("has_seatbelt") is False:
                    print(f"[t={timestamp:6.2f}s] seatbelt=MISSING")

            if frame is not None:
                cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(int(1000 / fps)) & 0xFF

            if key == 27 or key == ord("q"):
                break

            # Space: tạm dừng / tiếp tục để review kỹ từng đoạn
            if key == ord(" "):
                paused = not paused

    finally:
        cap.release()
        cv2.destroyAllWindows()
        if hasattr(drowsiness_detector, "landmarker") and hasattr(drowsiness_detector.landmarker, "close"):
            drowsiness_detector.landmarker.close()


if __name__ == "__main__":
    main()