"""EAR (Eye Aspect Ratio) calculation for drowsiness detection.

Reuses the exact algorithm from the standalone driver main.py.
DO NOT modify the mathematical logic.
"""

import numpy as np
from scipy.spatial import distance

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def calculate_ear(landmarks, eye_indices: list[int]) -> float:
    """Calculate Eye Aspect Ratio for a single eye.

    Args:
        landmarks: MediaPipe NormalizedLandmark list (each has .x, .y).
        eye_indices: List of 6 landmark indices for the eye.

    Returns:
        EAR value as float.
    """
    p1 = np.array([landmarks[eye_indices[0]].x, landmarks[eye_indices[0]].y])
    p2 = np.array([landmarks[eye_indices[1]].x, landmarks[eye_indices[1]].y])
    p3 = np.array([landmarks[eye_indices[2]].x, landmarks[eye_indices[2]].y])
    p4 = np.array([landmarks[eye_indices[3]].x, landmarks[eye_indices[3]].y])
    p5 = np.array([landmarks[eye_indices[4]].x, landmarks[eye_indices[4]].y])
    p6 = np.array([landmarks[eye_indices[5]].x, landmarks[eye_indices[5]].y])

    vertical1 = distance.euclidean(p2, p6)
    vertical2 = distance.euclidean(p3, p5)
    horizontal = distance.euclidean(p1, p4)

    ear = (vertical1 + vertical2) / (2.0 * horizontal)
    return float(ear)
