"""Eye Aspect Ratio (EAR) utility functions."""

import numpy as np
from scipy.spatial import distance

# Landmark indices for the eyes in MediaPipe Face Mesh (468/478 landmarks)
# LEFT_EYE indices correspond to: 33, 160, 158, 133, 153, 144
LEFT_EYE = [33, 160, 158, 133, 153, 144]

# RIGHT_EYE indices correspond to: 362, 385, 387, 263, 373, 380
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def calculate_ear(landmarks, eye_indices: list[int]) -> float:
    """Calculates the mathematical Eye Aspect Ratio (EAR) for a single eye.

    Args:
        landmarks: List of landmarks containing .x and .y attributes.
        eye_indices: List of 6 landmark indices for the eye.

    Returns:
        float: Calculated EAR value.
    """
    coords = [np.array([landmarks[idx].x, landmarks[idx].y]) for idx in eye_indices]
    
    # Vertical distances between the eye landmarks
    vertical1 = distance.euclidean(coords[1], coords[5])
    vertical2 = distance.euclidean(coords[2], coords[4])
    
    # Horizontal distance between the eye landmarks
    horizontal = distance.euclidean(coords[0], coords[3])
    
    # Calculate EAR
    ear = (vertical1 + vertical2) / (2.0 * horizontal)
    return ear
