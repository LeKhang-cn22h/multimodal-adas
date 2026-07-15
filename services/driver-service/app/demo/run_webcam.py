from __future__ import annotations

import cv2

from app.config import EYE_MODEL, MOUTH_MODEL
from app.services.drowsiness_detector import DrowsinessDetector


def main():

    detector = DrowsinessDetector(
        eye_model_path=EYE_MODEL,
        mouth_model_path=MOUTH_MODEL,
    )

    cap = cv2.VideoCapture(0)

    # Nếu nhiều camera:
    # cap = cv2.VideoCapture(1)

    if not cap.isOpened():
        print("Không mở được webcam.")
        return

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        frame, result = detector.process(frame)

        cv2.imshow("Driver Drowsiness Detection", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()