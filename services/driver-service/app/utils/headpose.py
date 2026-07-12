"""Head Pose estimation from facial transformation matrix.

Pure function — no I/O, no state, no side effects.
Testable with known rotation matrices.

ADR-004: Extracts Euler angles (Yaw, Pitch, Roll) directly from the
4x4 facial_transformation_matrix provided by MediaPipe Face Landmarker.
No solvePnP, no 3D model points.
"""

import math
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_head_pose(
    transformation_matrix: Optional[np.ndarray],
) -> tuple[float, float, float]:
    """Extract Yaw, Pitch, Roll (degrees) from a 4×4 transformation matrix.

    Decomposes the upper-left 3×3 rotation submatrix into Euler angles
    using atan2.  Angles are in degrees, range approximately [-90°, +90°]
    for pitch and roll, [-180°, +180°] for yaw.

    Args:
        transformation_matrix:  4×4 float64 matrix from
                                FaceLandmarkerResult.transformation_matrix.
                                May be None (no face detected / no matrix).

    Returns:
        (yaw_deg, pitch_deg, roll_deg) — each is float.
        Returns (0.0, 0.0, 0.0) when matrix is None.
    """
    if transformation_matrix is None:
        return 0.0, 0.0, 0.0

    # ── Extract rotation submatrix ────────────────────────────────────
    R = transformation_matrix[0:3, 0:3]

    # ── Decompose → Euler angles (Z-Y-X order, equivalent to yaw-pitch-roll) ──
    # Reference: Slabaugh, "Computing Euler angles from a rotation matrix"
    #   yaw   = atan2(R[1,0], R[0,0])
    #   pitch = atan2(-R[2,0], sqrt(R[2,1]^2 + R[2,2]^2))
    #   roll  = atan2(R[2,1], R[2,2])

    sy = math.sqrt(R[2, 1] * R[2, 1] + R[2, 2] * R[2, 2])

    # Guard against gimbal-lock singularity (sy near 0)
    if sy < 1e-6:
        yaw_rad = math.atan2(-R[1, 2], R[1, 1])
        pitch_rad = math.atan2(-R[2, 0], sy)
        roll_rad = 0.0
    else:
        yaw_rad = math.atan2(R[1, 0], R[0, 0])
        pitch_rad = math.atan2(-R[2, 0], sy)
        roll_rad = math.atan2(R[2, 1], R[2, 2])

    rad_to_deg = 180.0 / math.pi
    yaw_deg = float(yaw_rad * rad_to_deg)
    pitch_deg = float(pitch_rad * rad_to_deg)
    roll_deg = float(roll_rad * rad_to_deg)

    return yaw_deg, pitch_deg, roll_deg
