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


