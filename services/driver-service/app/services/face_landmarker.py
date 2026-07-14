"""
Face Landmarker sử dụng MediaPipe Tasks API.

Input:
    OpenCV BGR frame

Output:
    List[(x, y)] gồm 478 landmarks theo pixel.
"""

from __future__ import annotations

import cv2
import mediapipe as mp
import numpy as np

BaseOptions = mp.tasks.BaseOptions
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode
FaceLandmarkerTask = mp.tasks.vision.FaceLandmarker


class FaceLandmarker:

    def __init__(
        self,
        model_path: str = "app/models/face_landmarker.task",
        num_faces: int = 1,
    ) -> None:

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=model_path,
            ),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=num_faces,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )

        self.detector = FaceLandmarkerTask.create_from_options(
            options
        )

        self.timestamp = 0

    def detect(
        self,
        frame: np.ndarray,
    ) -> list[tuple[int, int]] | None:

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb,
        )

        result = self.detector.detect_for_video(
            mp_image,
            self.timestamp,
        )

        self.timestamp += 33

        if len(result.face_landmarks) == 0:
            return None

        h, w = frame.shape[:2]

        landmarks = []

        for lm in result.face_landmarks[0]:

            x = int(lm.x * w)

            y = int(lm.y * h)

            landmarks.append((x, y))

        return landmarks

    def close(self):

        self.detector.close()