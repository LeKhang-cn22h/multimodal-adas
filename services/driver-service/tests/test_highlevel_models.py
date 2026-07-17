"""High-level evaluation test for 4 driver-service models on highlevel dataset.

Evaluates:
    1. Face Detection (yolov8n-face.pt)      -> face / noface
    2. Eye CNN (eye_state_model.pt)           -> eyeopen / eyeclose
    3. Mouth CNN (mouth_state_model.pt)       -> yawn / noyawn
    4. Seatbelt YOLO (best.pt)                -> seatbelt / noseatbelt

Output:
    - Console: progress + summary report
    - File:    tests/highlevel_eval_results.txt (per-image predictions)

Usage:
    cd services/driver-service
    pytest tests/test_highlevel_models.py -s
"""

from __future__ import annotations

import re
import time
from collections import Counter
from pathlib import Path

import cv2
import pytest

# =============================================================================
# Paths (resolved relative to this file)
# =============================================================================

TEST_DIR = Path(__file__).resolve().parent          # .../tests/
DRIVER_DIR = TEST_DIR.parent                         # .../driver-service/
DATASET_DIR = DRIVER_DIR / "highlevel"
MODEL_DIR = DRIVER_DIR / "app" / "models"
OUTPUT_FILE = TEST_DIR / "highlevel_eval_results.txt"

FACE_MODEL = MODEL_DIR / "yolov8n-face.pt"
LANDMARK_MODEL = MODEL_DIR / "face_landmarker.task"
EYE_MODEL = MODEL_DIR / "eye_state_model.pt"
MOUTH_MODEL = MODEL_DIR / "mouth_state_model.pt"
SEATBELT_MODEL = MODEL_DIR / "best.pt"

# Column format for per-image log
# filename | face: pred/gt (result) | eye: pred/gt (result) | mouth: pred/gt (result) | seatbelt: pred/gt (result)
LOG_COLS = [
    "face",
    "eye",
    "mouth",
    "seatbelt",
]


# =============================================================================
# Ground truth parsing
# =============================================================================

_FILENAME_RE = re.compile(
    r"^(?P<eye>eyeopen|eyeclose)_"
    r"(?P<glass>glass|noglass)_"
    r"(?P<face>face|noface)_"
    r"(?P<yawn>yawn|noyawn)_"
    r"(?P<seatbelt>seatbelt|noseatbelt)_"
    r".*\.jpg$"
)


def parse_ground_truth(filename: str) -> dict | None:
    """Extract 5 ground-truth labels from a highlevel filename."""
    m = _FILENAME_RE.match(filename)
    if not m:
        return None
    return m.groupdict()


# =============================================================================
# Helpers
# =============================================================================

def _result_mark(pred: str, gt: str) -> str:
    """Return 'OK' if prediction matches ground truth, else 'FAIL'."""
    return "OK" if pred == gt else "FAIL"


def _print_confusion_matrix(labels: list[str], cm: Counter, file=None) -> None:
    """Print a text-based confusion matrix (2x2, or skip if <2 classes)."""
    if len(labels) < 2:
        msg = f"  (only {len(labels)} class(es) present — no matrix)"
        print(msg, file=file)
        return
    a, b = labels[0], labels[1]
    col_w = 12
    header = f"{'':>{col_w}}{'Pred ' + a:>{col_w}}{'Pred ' + b:>{col_w}}"
    print(header, file=file)
    row_a = f"{'Actual ' + a:<{col_w}}{cm.get((a, a), 0):>{col_w}}{cm.get((a, b), 0):>{col_w}}"
    row_b = f"{'Actual ' + b:<{col_w}}{cm.get((b, a), 0):>{col_w}}{cm.get((b, b), 0):>{col_w}}"
    print(row_a, file=file)
    print(row_b, file=file)


def _compute_metrics(y_true: list[str], y_pred: list[str],
                     positive: str) -> dict:
    """Binary classification metrics."""
    tp = sum(1 for t, p in zip(y_true, y_pred)
             if t == positive and p == positive)
    fp = sum(1 for t, p in zip(y_true, y_pred)
             if t != positive and p == positive)
    fn = sum(1 for t, p in zip(y_true, y_pred)
             if t == positive and p != positive)
    tn = sum(1 for t, p in zip(y_true, y_pred)
             if t != positive and p != positive)

    n = len(y_true)
    acc = (tp + tn) / n if n > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


# =============================================================================
# Model loading fixture (module scope — loaded ONCE)
# =============================================================================

@pytest.fixture(scope="module")
def models():
    """Load all 4 models; return a dict of ready-to-use components."""
    print("\n[LOADING] Initialising models ...")
    t0 = time.time()

    # 1. Face Detector (YOLO nano)
    from app.services.face_detector import FaceDetector
    face_detector = FaceDetector(
        model_path=str(FACE_MODEL), conf_threshold=0.5, device="cpu",
    )
    print(f"  FaceDetector   OK  ({time.time() - t0:.1f}s)")

    # 2. Face Landmarker (YOLO + MediaPipe) — reuse FaceDetector
    from app.services.face_landmarker import FaceLandmarker
    t1 = time.time()
    landmarker = FaceLandmarker(
        model_path=str(LANDMARK_MODEL), face_detector=face_detector,
    )
    print(f"  FaceLandmarker OK  ({time.time() - t1:.1f}s)")

    # 3. Croppers
    from app.services.eye_cropper import EyeCropper
    from app.services.mouth_cropper import MouthCropper
    eye_cropper = EyeCropper()
    mouth_cropper = MouthCropper()

    # 4. Predictor (Eye CNN + Mouth CNN)
    from app.services.classifiers.predictor import Predictor
    t2 = time.time()
    predictor = Predictor(
        eye_model_path=str(EYE_MODEL), mouth_model_path=str(MOUTH_MODEL),
    )
    print(f"  Predictor      OK  ({time.time() - t2:.1f}s)")

    # 5. Seatbelt Detector (YOLOv8m)
    from app.services.seatbelt_detector import SeatbeltDetector
    t3 = time.time()
    seatbelt_detector = SeatbeltDetector(
        model_path=str(SEATBELT_MODEL), confidence_threshold=0.3,
    )
    print(f"  SeatbeltDet.   OK  ({time.time() - t3:.1f}s)")

    print(f"[LOADING] All models ready in {time.time() - t0:.1f}s\n")

    return {
        "face_detector": face_detector,
        "landmarker": landmarker,
        "eye_cropper": eye_cropper,
        "mouth_cropper": mouth_cropper,
        "predictor": predictor,
        "seatbelt_detector": seatbelt_detector,
    }


# =============================================================================
# Main evaluation test
# =============================================================================

def test_highlevel_models(models: dict) -> None:
    """Run 4-model evaluation; write per-image log to txt file."""
    image_files = sorted(DATASET_DIR.glob("*.jpg"))
    n_total = len(image_files)

    print(f"{'=' * 60}")
    print(f"  HIGHLEVEL MODEL EVALUATION")
    print(f"{'=' * 60}")
    print(f"  Dataset : {n_total} images")
    print(f"  Output  : {OUTPUT_FILE}")
    print(f"  Models  : Face (yolov8n-face), Eye (CNN), Mouth (CNN),")
    print(f"            Seatbelt (YOLOv8m)")
    print(f"{'=' * 60}")

    # Unpack
    face_detector = models["face_detector"]
    landmarker = models["landmarker"]
    eye_cropper = models["eye_cropper"]
    mouth_cropper = models["mouth_cropper"]
    predictor = models["predictor"]
    seatbelt_detector = models["seatbelt_detector"]

    # Accumulators (for summary)
    face_gt: list[str] = []
    face_pd: list[str] = []
    eye_gt: list[str] = []
    eye_pd: list[str] = []
    eye_glass_gt: list[str] = []
    eye_glass_pd: list[str] = []
    eye_noglass_gt: list[str] = []
    eye_noglass_pd: list[str] = []
    mouth_gt: list[str] = []
    mouth_pd: list[str] = []
    seatbelt_gt: list[str] = []
    seatbelt_pd: list[str] = []

    parse_errors = 0
    invalid_images = 0
    face_detected_count = 0
    crop_fail_count = 0

    # Per-image log lines
    log_lines: list[str] = []

    t_start = time.time()

    # ── Main loop ─────────────────────────────────────────────────────
    for idx, img_path in enumerate(image_files):
        if (idx + 1) % 100 == 0 or idx == 0:
            pct = (idx + 1) / n_total * 100
            elapsed = time.time() - t_start
            eta = elapsed / (idx + 1) * (n_total - idx - 1) if idx > 0 else 0
            print(f"  [{idx + 1:>4}/{n_total}  {pct:5.1f}%]  "
                  f"elapsed={elapsed:.0f}s  eta={eta:.0f}s")

        fname = img_path.name

        # Ground truth
        gt = parse_ground_truth(fname)
        if gt is None:
            parse_errors += 1
            log_lines.append(f"{fname} | PARSE_ERROR")
            continue

        # Read image
        frame = cv2.imread(str(img_path))
        if frame is None:
            invalid_images += 1
            log_lines.append(f"{fname} | INVALID_IMAGE")
            continue

        # ── 1. Face Detection ─────────────────────────────────────
        bboxes = face_detector.detect(frame)
        has_face = len(bboxes) > 0
        pred_face = "face" if has_face else "noface"
        gt_face = gt["face"]
        face_gt.append(gt_face)
        face_pd.append(pred_face)
        face_result = _result_mark(pred_face, gt_face)

        # ── 2 & 3. Eye + Mouth ────────────────────────────────────
        pred_eye = "-"
        pred_mouth = "-"
        eye_result = "-"
        mouth_result = "-"

        if has_face:
            face_detected_count += 1
            all_lm = landmarker.detect_all(frame)

            if all_lm:
                landmarks = all_lm[0]
                left_eye = eye_cropper.crop_left(frame, landmarks)
                right_eye = eye_cropper.crop_right(frame, landmarks)
                mouth_roi = mouth_cropper.crop(frame, landmarks)

                if (left_eye is not None
                        and right_eye is not None
                        and mouth_roi is not None):
                    result = predictor.predict(left_eye, right_eye, mouth_roi)

                    raw_eye = result["eye"]["label"]
                    pred_eye = "eyeopen" if raw_eye == "OPEN" else "eyeclose"
                    gt_eye = gt["eye"]
                    eye_result = _result_mark(pred_eye, gt_eye)

                    raw_mouth = result["mouth"]["label"]
                    pred_mouth = "yawn" if raw_mouth == "YAWN" else "noyawn"
                    gt_mouth = gt["yawn"]
                    mouth_result = _result_mark(pred_mouth, gt_mouth)

                    eye_gt.append(gt_eye)
                    eye_pd.append(pred_eye)
                    mouth_gt.append(gt_mouth)
                    mouth_pd.append(pred_mouth)

                    if gt["glass"] == "glass":
                        eye_glass_gt.append(gt_eye)
                        eye_glass_pd.append(pred_eye)
                    else:
                        eye_noglass_gt.append(gt_eye)
                        eye_noglass_pd.append(pred_eye)
                else:
                    crop_fail_count += 1
            else:
                crop_fail_count += 1

        # ── 4. Seatbelt ───────────────────────────────────────────
        sb = seatbelt_detector.detect(frame)
        pred_sb = "seatbelt" if sb["has_seatbelt"] else "noseatbelt"
        gt_sb = gt["seatbelt"]
        seatbelt_gt.append(gt_sb)
        seatbelt_pd.append(pred_sb)
        sb_result = _result_mark(pred_sb, gt_sb)

        # ── Build log line ────────────────────────────────────────
        parts = [
            f"{fname}",
            f"face: {pred_face}/{gt_face} ({face_result})",
            f"eye: {pred_eye}/{gt['eye']} ({eye_result})",
            f"mouth: {pred_mouth}/{gt['yawn']} ({mouth_result})",
            f"seatbelt: {pred_sb}/{gt_sb} ({sb_result})",
        ]
        log_lines.append(" | ".join(parts))

    t_total = time.time() - t_start

    # ==================================================================
    # WRITE TXT OUTPUT FILE
    # ==================================================================

    processed = n_total - parse_errors - invalid_images
    n_eye = len(eye_gt)
    n_mouth = len(mouth_gt)
    n_sb = len(seatbelt_gt)
    n_face = len(face_gt)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # Header
        f.write("# ================================================================\n")
        f.write(f"# HIGHLEVEL MODEL EVALUATION RESULTS\n")
        f.write(f"# Dataset: {n_total} images\n")
        f.write(f"# Date:    {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# ================================================================\n")
        f.write("# Format: filename | face: pred/gt (OK/FAIL) | "
                "eye: pred/gt (OK/FAIL/-) | mouth: pred/gt (OK/FAIL/-) | "
                "seatbelt: pred/gt (OK/FAIL)\n")
        f.write("#   '-' = skipped (no face / crop fail)\n")
        f.write("# ================================================================\n\n")

        # Per-image log
        for line in log_lines:
            f.write(line + "\n")

        # ── Summary ───────────────────────────────────────────────
        f.write(f"\n{'=' * 60}\n")
        f.write(f"SUMMARY\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Total images     : {n_total}\n")
        f.write(f"Parse errors     : {parse_errors}\n")
        f.write(f"Invalid (unread) : {invalid_images}\n")
        f.write(f"Processed        : {processed}\n")
        f.write(f"Face detected    : {face_detected_count}\n")
        f.write(f"Crop failures    : {crop_fail_count}\n")
        f.write(f"Eye evaluated    : {n_eye}\n")
        f.write(f"Mouth evaluated  : {n_mouth}\n")
        f.write(f"Seatbelt eval'd  : {n_sb}\n")
        f.write(f"Total runtime    : {t_total:.1f}s  "
                f"({t_total / max(processed, 1) * 1000:.1f} ms/image)\n")

        # ── Per-model metrics ─────────────────────────────────────
        for model_name, gt_list, pd_list, pos_label, labels in [
            ("FACE DETECTION (yolov8n-face)",
             face_gt, face_pd, "face", ["face", "noface"]),
            ("EYE CNN (eye_state_model.pt)",
             eye_gt, eye_pd, "eyeclose", ["eyeopen", "eyeclose"]),
            ("MOUTH CNN (mouth_state_model.pt)",
             mouth_gt, mouth_pd, "yawn", ["yawn", "noyawn"]),
            ("SEATBELT (best.pt / YOLOv8m)",
             seatbelt_gt, seatbelt_pd, "noseatbelt", ["seatbelt", "noseatbelt"]),
        ]:
            n = len(gt_list)
            f.write(f"\n{'─' * 50}\n")
            f.write(f"  {model_name}\n")
            f.write(f"{'─' * 50}\n")
            f.write(f"  Evaluated: {n} frames\n")
            if n > 0:
                ok = sum(1 for t, p in zip(gt_list, pd_list) if t == p)
                f.write(f"  Accuracy : {ok / n * 100:.1f}%  ({ok}/{n})\n")
                _print_confusion_matrix(labels, Counter(zip(gt_list, pd_list)), file=f)
                m = _compute_metrics(gt_list, pd_list, pos_label)
                f.write(f"  Precision({pos_label}) : {m['precision']:.3f}\n")
                f.write(f"  Recall({pos_label})    : {m['recall']:.3f}\n")
                f.write(f"  F1({pos_label})        : {m['f1']:.3f}\n")
            else:
                f.write("  (no predictions)\n")

        # Eye by glass breakdown
        if eye_glass_gt or eye_noglass_gt:
            f.write(f"\n{'─' * 50}\n")
            f.write(f"  EYE CNN — BY GLASS\n")
            f.write(f"{'─' * 50}\n")
            ng = len(eye_glass_gt)
            nn = len(eye_noglass_gt)
            if ng > 0:
                gok = sum(1 for t, p in zip(eye_glass_gt, eye_glass_pd) if t == p)
                f.write(f"  With glass    ({ng:>4}): {gok / ng * 100:.1f}%\n")
            if nn > 0:
                nok = sum(1 for t, p in zip(eye_noglass_gt, eye_noglass_pd) if t == p)
                f.write(f"  Without glass ({nn:>4}): {nok / nn * 100:.1f}%\n")

        f.write(f"\n{'=' * 60}\n")
        f.write(f"END OF REPORT\n")
        f.write(f"{'=' * 60}\n")

    # ==================================================================
    # CONSOLE SUMMARY
    # ==================================================================

    print(f"\n{'=' * 60}")
    print(f"  EVALUATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Output file : {OUTPUT_FILE}")
    print(f"  Processed   : {processed}/{n_total}")
    print(f"  Parse errors: {parse_errors}")
    print(f"  Runtime     : {t_total:.1f}s")

    # Quick per-model accuracy
    for name, gt_list, pd_list in [
        ("Face  ", face_gt, face_pd),
        ("Eye   ", eye_gt, eye_pd),
        ("Mouth ", mouth_gt, mouth_pd),
        ("Seatbelt", seatbelt_gt, seatbelt_pd),
    ]:
        n = len(gt_list)
        if n > 0:
            ok = sum(1 for t, p in zip(gt_list, pd_list) if t == p)
            print(f"  {name}: {ok / n * 100:5.1f}%  ({ok}/{n})")
        else:
            print(f"  {name}: N/A")

    print(f"{'=' * 60}\n")
    print(f"  Full report: {OUTPUT_FILE}\n")

    # ── Hard assertions ───────────────────────────────────────────────
    assert parse_errors == 0, (
        f"{parse_errors} files could not be parsed — check filename format"
    )
    assert processed == n_total, (
        f"Only {processed}/{n_total} images processed"
    )
