"""MAR (Mouth Aspect Ratio) calculation for yawn detection.

Pure function — no I/O, no state, no side effects.
Testable with mock landmarks.

Landmark indices based on MediaPipe Face Landmarker 478-point topology.
"""

import numpy as np
from scipy.spatial import distance

# ---------------------------------------------------------------------------
# Mouth landmark indices — Face Landmarker 478-point topology
# ---------------------------------------------------------------------------

MOUTH_INNER_UPPER = [13]    # upper inner lip center
MOUTH_INNER_LOWER = [14]    # lower inner lip center
MOUTH_CORNER_LEFT = [61]    # left mouth corner
MOUTH_CORNER_RIGHT = [291]  # right mouth corner

# Reserve indices for possible outer-lip variant
MOUTH_OUTER_UPPER = [0]     # upper outer lip center (philtrum)
MOUTH_OUTER_LOWER = [17]    # lower outer lip center


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_mar(landmarks) -> float:
    """Calculate Mouth Aspect Ratio from 478 facial landmarks.

    MAR = vertical_inner / horizontal_corners.

    A high MAR (> 0.6) typically indicates yawning.

    Args:
        landmarks:  list[mediapipe NormalizedLandmark] length 478.
                    Each element exposes .x, .y, .z attributes.

    Returns:
        MAR value as float.  Returns 0.0 when mouth corners coincide
        (degenerate case — should never happen with real landmarks).
    """
    # ── Vertical: inner lip opening ──────────────────────────────────
    inner_upper = np.array([
        landmarks[MOUTH_INNER_UPPER[0]].x,
        landmarks[MOUTH_INNER_UPPER[0]].y,
    ])
    inner_lower = np.array([
        landmarks[MOUTH_INNER_LOWER[0]].x,
        landmarks[MOUTH_INNER_LOWER[0]].y,
    ])
    vertical = distance.euclidean(inner_upper, inner_lower)

    # ── Horizontal: mouth width ──────────────────────────────────────
    corner_left = np.array([
        landmarks[MOUTH_CORNER_LEFT[0]].x,
        landmarks[MOUTH_CORNER_LEFT[0]].y,
    ])
    corner_right = np.array([
        landmarks[MOUTH_CORNER_RIGHT[0]].x,
        landmarks[MOUTH_CORNER_RIGHT[0]].y,
    ])
    horizontal = distance.euclidean(corner_left, corner_right)

    if horizontal < 1e-8:
        return 0.0

    mar = vertical / horizontal
    return float(mar)
