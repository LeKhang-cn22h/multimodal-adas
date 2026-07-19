"""
Face Landmarker: YOLO-Face tìm bbox -> crop -> MediaPipe FaceLandmarker
lấy 478 landmarks trên từng crop.

Input:
    OpenCV BGR frame

Output:
    detect()      -> List[(x, y)] của khuôn mặt ĐẦU TIÊN detect được.
    detect_all()  -> List[List[(x, y)]] của TẤT CẢ khuôn mặt, tọa độ đã
                     quy về hệ frame gốc (không phải hệ tọa độ crop).
"""

from __future__ import annotations

import cv2
import mediapipe as mp
import numpy as np

from app.services.face_detector import FaceDetector

BaseOptions = mp.tasks.BaseOptions
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode
FaceLandmarkerTask = mp.tasks.vision.FaceLandmarker


class FaceLandmarker:

    def __init__(
        self,
        model_path: str = "app/models/face_landmarker.task",
        face_detector: FaceDetector | None = None,
        padding_ratio: float = 0.25,
    ) -> None:

        # padding_ratio: mở rộng bbox YOLO thêm % trước khi crop, vì
        # MediaPipe cần thấy đủ trán/cằm/tai xung quanh mới landmark
        # chính xác — bbox YOLO thường sát mặt hơn MediaPipe tự detect.
        self.padding_ratio = padding_ratio

        self.face_detector = face_detector or FaceDetector()

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=model_path,
            ),
            # IMAGE thay vì VIDEO: mỗi crop được xử lý độc lập (không còn
            # 1 mặt track liên tục xuyên suốt video ở cấp MediaPipe nữa,
            # vì tracking giờ là việc của YOLO + DriverSelector), nên bỏ
            # luôn yêu cầu timestamp tăng đơn điệu — vốn dễ vỡ khi gọi
            # detector nhiều lần/frame (1 lần/mặt).
            running_mode=VisionRunningMode.IMAGE,
            num_faces=1,  # mỗi crop chỉ có đúng 1 mặt sau khi YOLO tách
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )

        self.detector = FaceLandmarkerTask.create_from_options(options)

    def _pad_bbox(
        self,
        bbox: tuple[int, int, int, int],
        frame_shape: tuple[int, int],
    ) -> tuple[int, int, int, int]:

        x1, y1, x2, y2 = bbox
        fh, fw = frame_shape[:2]

        w = x2 - x1
        h = y2 - y1
        pad_w = w * self.padding_ratio
        pad_h = h * self.padding_ratio

        nx1 = max(0, int(x1 - pad_w))
        ny1 = max(0, int(y1 - pad_h))
        nx2 = min(fw, int(x2 + pad_w))
        ny2 = min(fh, int(y2 + pad_h))

        return nx1, ny1, nx2, ny2

    def _to_pixel_landmarks(
        self,
        face_landmarks,
        crop_shape: tuple[int, int],
        offset: tuple[int, int],
    ) -> list[tuple[int, int]]:

        h, w = crop_shape[:2]
        ox, oy = offset

        landmarks = []
        for lm in face_landmarks:
            x = int(lm.x * w) + ox
            y = int(lm.y * h) + oy
            landmarks.append((x, y))

        return landmarks

    def _run_on_crop(self, crop: np.ndarray):

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        return self.detector.detect(mp_image)

    def detect(
        self,
        frame: np.ndarray,
        timestamp_ms: int | None = None,  # giữ tham số để tương thích ngược,
                                           # KHÔNG còn dùng ở đây (xem detect_all)
    ) -> list[tuple[int, int]] | None:

        all_landmarks = self.detect_all(frame, timestamp_ms)

        if not all_landmarks:
            return None

        return all_landmarks[0]

    def detect_all(
        self,
        frame: np.ndarray,
        timestamp_ms: int | None = None,  # không dùng, giữ để tương thích
                                           # với chữ ký cũ (DrowsinessDetector
                                           # vẫn truyền timestamp cho buffer
                                           # khác, không phải cho hàm này)
    ) -> list[list[tuple[int, int]]]:

        bboxes = self.face_detector.detect(frame)

        if not bboxes:
            return []

        all_landmarks: list[list[tuple[int, int]]] = []

        for bbox in bboxes:
            x1, y1, x2, y2 = self._pad_bbox(bbox, frame.shape)

            if x2 <= x1 or y2 <= y1:
                continue

            crop = frame[y1:y2, x1:x2]

            result = self._run_on_crop(crop)

            if len(result.face_landmarks) == 0:
                continue

            landmarks = self._to_pixel_landmarks(
                result.face_landmarks[0],
                crop.shape,
                offset=(x1, y1),
            )
            all_landmarks.append(landmarks)

        return all_landmarks

    def close(self):
        self.detector.close()