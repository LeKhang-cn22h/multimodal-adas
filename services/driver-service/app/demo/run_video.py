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

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        frame, result = detector.process(frame)

        cv2.imshow("Driver Drowsiness Detection", frame)

        key = cv2.waitKey(int(1000 / fps))

        if key == 27 or key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()