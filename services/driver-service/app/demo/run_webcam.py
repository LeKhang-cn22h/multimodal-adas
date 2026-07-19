from __future__ import annotations

import time

import cv2

from app.config import EYE_MODEL, MOUTH_MODEL
from app.services.classifiers.predictor import Predictor
from app.services.eye_cropper import EyeCropper
from app.services.face_landmarker import FaceLandmarker
from app.services.mouth_cropper import MouthCropper


def main():

    landmarker = FaceLandmarker()
    eye_cropper = EyeCropper()
    mouth_cropper = MouthCropper()

    predictor = Predictor(
        eye_model_path=EYE_MODEL,
        mouth_model_path=MOUTH_MODEL,
    )

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Không mở được webcam.")
        return

    save_count = 0

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        landmarks = landmarker.detect(frame)

        if landmarks is not None:

            mouth_roi = mouth_cropper.crop(frame, landmarks)

            if mouth_roi is not None:

                # Hiện ROI phóng to để nhìn rõ
                debug_view = cv2.resize(mouth_roi, (200, 200))
                cv2.imshow("Mouth ROI DEBUG", debug_view)

                # Predict trực tiếp trên ROI này để in probability real-time
                result = predictor.predict_mouth(mouth_roi)

                cv2.putText(
                    frame,
                    f"Mouth: {result['label']} ({result['probability']:.4f})",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )

                print(
                    f"probability={result['probability']:.4f}  label={result['label']}"
                )

        cv2.imshow("Webcam", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:
            break

        # Nhấn 's' để lưu ảnh mouth_roi hiện tại ra file, dùng test lại bằng test_mouth_model.py
        if key == ord("s") and landmarks is not None and mouth_roi is not None:
            save_count += 1
            filename = f"debug_mouth_{save_count}_{int(time.time()*1000)}.jpg"
            cv2.imwrite(filename, mouth_roi)
            print(f"Đã lưu: {filename}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
    