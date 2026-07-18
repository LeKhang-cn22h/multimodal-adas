from __future__ import annotations

import cv2

from app.services.face_landmarker import FaceLandmarker
from app.services.eye_cropper import EyeCropper
from app.services.mouth_cropper import MouthCropper


def main():

    face_landmarker = FaceLandmarker()

    eye_cropper = EyeCropper()

    mouth_cropper = MouthCropper()

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Không mở được webcam.")
        return

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        landmarks = face_landmarker.detect(frame)

        display = frame.copy()

        if landmarks is not None:

            # --------- vẽ landmark ---------

            for x, y in landmarks:

                cv2.circle(
                    display,
                    (x, y),
                    1,
                    (0, 255, 0),
                    -1,
                )

            # --------- crop mắt ---------

            eye_roi = eye_cropper.crop(
                frame,
                landmarks,
            )

            if eye_roi is not None:

                cv2.imshow(
                    "Eye ROI",
                    eye_roi,
                )

            # --------- crop miệng ---------

            mouth_roi = mouth_cropper.crop(
                frame,
                landmarks,
            )

            if mouth_roi is not None:

                cv2.imshow(
                    "Mouth ROI",
                    mouth_roi,
                )

        cv2.imshow(
            "Face",
            display,
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:
            break

    cap.release()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()