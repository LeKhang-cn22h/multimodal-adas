import cv2
import mediapipe as mp
import time
import numpy as np
from scipy.spatial import distance

# ==========================
# MediaPipe Face Landmarker
# ==========================

BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = FaceLandmarkerOptions(
    base_options=BaseOptions(
        model_asset_path="face_landmarker.task"
    ),
    running_mode=VisionRunningMode.VIDEO,
    num_faces=1
)

# ==========================
# EAR CONFIG
# ==========================

EAR_THRESHOLD = 0.22
DROWSY_FRAMES = 60

closed_eye_frames = 0

# ==========================
# Landmark Index
# ==========================

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# ==========================
# EAR FUNCTION
# ==========================

def calculate_ear(landmarks, eye_indices):

    p1 = np.array([landmarks[eye_indices[0]].x,
                   landmarks[eye_indices[0]].y])

    p2 = np.array([landmarks[eye_indices[1]].x,
                   landmarks[eye_indices[1]].y])

    p3 = np.array([landmarks[eye_indices[2]].x,
                   landmarks[eye_indices[2]].y])

    p4 = np.array([landmarks[eye_indices[3]].x,
                   landmarks[eye_indices[3]].y])

    p5 = np.array([landmarks[eye_indices[4]].x,
                   landmarks[eye_indices[4]].y])

    p6 = np.array([landmarks[eye_indices[5]].x,
                   landmarks[eye_indices[5]].y])

    vertical1 = distance.euclidean(p2, p6)
    vertical2 = distance.euclidean(p3, p5)

    horizontal = distance.euclidean(p1, p4)

    ear = (vertical1 + vertical2) / (2.0 * horizontal)

    return ear


# ==========================
# Camera
# ==========================

cap = cv2.VideoCapture(0)

with FaceLandmarker.create_from_options(options) as landmarker:

    while cap.isOpened():

        success, frame = cap.read()

        if not success:
            break

        frame = cv2.flip(frame, 1)

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        timestamp_ms = int(time.time() * 1000)

        result = landmarker.detect_for_video(
            mp_image,
            timestamp_ms
        )

        if result.face_landmarks:

            landmarks = result.face_landmarks[0]

            # ==================
            # Draw landmarks
            # ==================

            for landmark in landmarks:

                x = int(
                    landmark.x * frame.shape[1]
                )

                y = int(
                    landmark.y * frame.shape[0]
                )

                cv2.circle(
                    frame,
                    (x, y),
                    1,
                    (0, 255, 0),
                    -1
                )

            # ==================
            # EAR
            # ==================

            left_ear = calculate_ear(
                landmarks,
                LEFT_EYE
            )

            right_ear = calculate_ear(
                landmarks,
                RIGHT_EYE
            )

            ear = (left_ear + right_ear) / 2

            cv2.putText(
                frame,
                f"EAR: {ear:.3f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

            # ==================
            # Drowsy Logic
            # ==================

            if ear < EAR_THRESHOLD:

                closed_eye_frames += 1

            else:

                closed_eye_frames = 0

            cv2.putText(
                frame,
                f"Closed Frames: {closed_eye_frames}",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 0),
                2
            )

            # ==================
            # Alert
            # ==================

            if closed_eye_frames > DROWSY_FRAMES:

                cv2.putText(
                    frame,
                    "DROWSY ALERT!",
                    (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,
                    (0, 0, 255),
                    3
                )

        cv2.imshow(
            "Driver Monitoring",
            frame
        )

        if cv2.waitKey(1) & 0xFF == 27:
            break

cap.release()
cv2.destroyAllWindows()