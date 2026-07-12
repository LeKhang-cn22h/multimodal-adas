"""Step 2 — Extract 7 root features from NTHU-DDD dataset images.

Uses FaceLandmarkerService (same code path as runtime) to detect
facial landmarks, then computes EAR, MAR, HeadPose via app.utils.*
pure functions.

Dataset structure (asymmetric — TS-dataset-training.md Step 1):
    drowsy/
      sleepyCombination/        → label = 1
      yawning/                  → label = 1
      slowBlinkWithNodding/     → label = 1
    notdrowsy/                  → label = 0  (flat, no sub-folders)

Filename: {subject}_{glasses}_{scenario}_{frameNumber}_{labelStr}.jpg
Label mapping: "drowsy" → 1, "notdrowsy" → 0

Output: training/output/dataset_intermediate.csv
"""

import csv
import sys
import time
from pathlib import Path

import cv2
from tqdm import tqdm

# Allow imports from app/ (training scripts run from driver-service root)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.mediapipe_service import FaceLandmarkerService
from app.utils.ear import LEFT_EYE, RIGHT_EYE, calculate_ear
from app.utils.headpose import extract_head_pose
from app.utils.logger import get_logger
from app.utils.mar import calculate_mar

logger = get_logger()

DATASET_ROOT = Path("dataset/Multi class/train")
OUTPUT_CSV = Path("training/output/dataset_intermediate.csv")

DROWSY_SCENARIOS = ["sleepyCombination", "yawning", "slowBlinkWithNodding"]


def parse_filename(filename: str) -> dict:
    """Parse NTHU-DDD filename into structured fields.

    Example: 001_glasses_sleepyCombination_1000_drowsy.jpg
    → subject=001, glasses=glasses, scenario=sleepyCombination,
      frame=1000, label_str="drowsy"
    """
    name = filename.replace(".jpg", "")
    parts = name.split("_")
    return {
        "subject_id": parts[0],
        "glasses": parts[1],
        "scenario": "_".join(parts[2:-2]),
        "frame_number": int(parts[-2]),
        "label_str": parts[-1],
    }


def collect_image_paths() -> list[dict]:
    """Walk the asymmetric dataset, return list of {img_path, meta...}."""
    entries: list[dict] = []

    # ── Drowsy (3 sub-folders) ────────────────────────────────────
    drowsy_root = DATASET_ROOT / "drowsy"
    for scenario in DROWSY_SCENARIOS:
        scenario_dir = drowsy_root / scenario
        if not scenario_dir.is_dir():
            logger.warning("Missing directory: %s", scenario_dir)
            continue
        for img_path in sorted(scenario_dir.glob("*.jpg")):
            meta = parse_filename(img_path.name)
            meta["img_path"] = str(img_path)
            meta["label_binary"] = 1
            entries.append(meta)

    # ── Not-drowsy (flat) ─────────────────────────────────────────
    notdrowsy_root = DATASET_ROOT / "notdrowsy"
    if notdrowsy_root.is_dir():
        for img_path in sorted(notdrowsy_root.glob("*.jpg")):
            meta = parse_filename(img_path.name)
            meta["img_path"] = str(img_path)
            meta["label_binary"] = 0
            entries.append(meta)

    return entries


def main() -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Loading FaceLandmarkerService...")
    landmark_service = FaceLandmarkerService(model_path="face_landmarker.task")
    landmark_service.load_model()
    logger.info("Model loaded")

    entries = collect_image_paths()
    logger.info("Found %d images", len(entries))

    skipped = 0
    start_time = time.time()

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "subject_id", "scenario", "frame_number",
            "ear_left", "ear_right", "ear_avg",
            "mar", "yaw", "pitch", "roll",
            "label_binary",
        ])

        for entry in tqdm(entries, desc="Extracting features"):
            frame = cv2.imread(entry["img_path"])
            if frame is None:
                skipped += 1
                continue

            timestamp_ms = int(time.time() * 1000)
            result = landmark_service.detect(frame, timestamp_ms)

            if not result.face_detected or result.landmarks is None:
                skipped += 1
                continue

            landmarks = result.landmarks
            ear_left = float(calculate_ear(landmarks, LEFT_EYE))
            ear_right = float(calculate_ear(landmarks, RIGHT_EYE))
            ear_avg = (ear_left + ear_right) / 2.0
            mar = float(calculate_mar(landmarks))

            yaw, pitch, roll = 0.0, 0.0, 0.0
            if result.transformation_matrix is not None:
                yaw, pitch, roll = extract_head_pose(result.transformation_matrix)

            writer.writerow([
                entry["subject_id"],
                entry["scenario"],
                entry["frame_number"],
                round(ear_left, 6),
                round(ear_right, 6),
                round(ear_avg, 6),
                round(mar, 6),
                round(float(yaw), 4),
                round(float(pitch), 4),
                round(float(roll), 4),
                entry["label_binary"],
            ])

    elapsed = time.time() - start_time
    logger.info(
        "Done: %d rows written, %d skipped, %.1f min",
        len(entries) - skipped, skipped, elapsed / 60.0,
    )
    logger.info("Output: %s", OUTPUT_CSV)

    landmark_service.close_model()


if __name__ == "__main__":
    main()
