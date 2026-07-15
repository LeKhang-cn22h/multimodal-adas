"""Prepare MRL Eye Dataset + Yawn Dataset for CNN training.

MRL Eye Dataset: label is encoded IN THE FILENAME (no folder split):
    s0001_00001_0_0_0_0_0_01.png
    fields (split by '_'): subjectID, imageID, gender, glasses,
    eye_state(0=closed,1=open), reflections, lighting, sensorID.png
    -> we do a SUBJECT-LEVEL split (not random image split), so no
       subject appears in both train and val — this matters a lot,
       otherwise validation accuracy is overly optimistic (the model
       could just memorize a subject's eye shape instead of learning
       "closed vs open" in general).

Yawn Dataset: label is encoded by FOLDER name (yawn / no_yawn), exact
    folder name auto-detected (case-insensitive, tolerant of
    'no_yawn' vs 'noyawn' vs 'not_yawn' etc).
    -> no subject metadata available, so we do a random 80/20 split.

Output layout (ready for Keras ImageDataGenerator / torchvision ImageFolder):
    training/output/cnn_data/eye_state/train/{open,closed}/*.png
    training/output/cnn_data/eye_state/val/{open,closed}/*.png
    training/output/cnn_data/mouth_state/train/{yawn,no_yawn}/*.jpg
    training/output/cnn_data/mouth_state/val/{yawn,no_yawn}/*.jpg

Run:
    python training/prepare_cnn_datasets.py ^
        --mrl-source "C:\\path\\to\\mrl-eye-dataset" ^
        --yawn-source "C:\\path\\to\\yawn-dataset"
"""

import argparse
import random
import shutil
from pathlib import Path

from tqdm import tqdm

random.seed(42)

OUTPUT_ROOT = Path("training/output/cnn_data")
VAL_RATIO = 0.2


# =========================================================================
# MRL Eye Dataset (filename-encoded labels, subject-level split)
# =========================================================================


def prepare_mrl(source: Path, dry_run: bool) -> None:
    out_dir = OUTPUT_ROOT / "eye_state"
    files = list(source.rglob("*.png"))
    if not files:
        print(f"Không tìm thấy file .png nào trong {source} — kiểm tra lại đường dẫn.")
        return

    by_subject: dict[str, list[Path]] = {}
    skipped = 0
    for f in files:
        parts = f.stem.split("_")
        if len(parts) < 5:
            skipped += 1
            continue
        subject = parts[0]
        by_subject.setdefault(subject, []).append(f)

    subjects = sorted(by_subject.keys())
    subject_counts = {s: len(by_subject[s]) for s in subjects}
    total_images = sum(subject_counts.values())
    target_val_images = total_images * VAL_RATIO

    # Subject-level split (no leakage), but search for the subset of
    # subjects whose TOTAL IMAGE COUNT is closest to the 80/20 target —
    # subject count alone (e.g. 7/37) doesn't give 20% of IMAGES since
    # subjects have very different numbers of photos.
    best_val_subjects, best_diff = None, float("inf")
    n_trials = 5000
    for _ in range(n_trials):
        shuffled = subjects.copy()
        random.shuffle(shuffled)
        running_total = 0
        candidate = []
        for s in shuffled:
            if running_total + subject_counts[s] > target_val_images * 1.15:
                continue  # skip if it would overshoot too much
            candidate.append(s)
            running_total += subject_counts[s]
            if running_total >= target_val_images * 0.95:
                break
        diff = abs(running_total - target_val_images)
        if diff < best_diff:
            best_diff = diff
            best_val_subjects = candidate

    val_subjects = set(best_val_subjects)
    actual_val_images = sum(subject_counts[s] for s in val_subjects)
    actual_ratio = actual_val_images / total_images * 100

    print(f"MRL: {len(files)} ảnh, {len(subjects)} subject, {skipped} file bỏ qua (tên không đúng format)")
    print(
        f"  -> {len(val_subjects)} subject dùng cho VAL "
        f"({actual_val_images} ảnh, {actual_ratio:.1f}% -- mục tiêu {VAL_RATIO*100:.0f}%), "
        f"{len(subjects) - len(val_subjects)} subject dùng cho TRAIN"
    )

    counts = {"train": {"open": 0, "closed": 0}, "val": {"open": 0, "closed": 0}}

    for subject, subject_files in tqdm(by_subject.items(), desc="MRL: copying by subject"):
        split = "val" if subject in val_subjects else "train"
        for f in subject_files:
            parts = f.stem.split("_")
            eye_state = parts[4]
            label = "open" if eye_state == "1" else "closed" if eye_state == "0" else None
            if label is None:
                continue

            dst_dir = out_dir / split / label
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_path = dst_dir / f.name
            if not dry_run:
                shutil.copy2(f, dst_path)
            counts[split][label] += 1

    print(f"  TRAIN: open={counts['train']['open']}  closed={counts['train']['closed']}")
    print(f"  VAL:   open={counts['val']['open']}  closed={counts['val']['closed']}")
    if dry_run:
        print("  (--dry-run: chưa copy file thật)")


# =========================================================================
# Yawn Dataset (folder-encoded labels, random split)
# =========================================================================


def detect_yawn_folders(source: Path) -> tuple[Path | None, Path | None]:
    """Auto-detect which sub-folder is 'yawn' vs 'no_yawn' by name,
    tolerant to naming variations."""
    yawn_dir, no_yawn_dir = None, None
    for d in source.rglob("*"):
        if not d.is_dir():
            continue
        name = d.name.lower().replace("-", "_").replace(" ", "_")
        has_images = any(d.glob("*.jpg")) or any(d.glob("*.png"))
        if not has_images:
            continue
        if "no" in name and "yawn" in name:
            no_yawn_dir = d
        elif "yawn" in name:
            yawn_dir = d
    return yawn_dir, no_yawn_dir


def prepare_yawn(source: Path, dry_run: bool) -> None:
    out_dir = OUTPUT_ROOT / "mouth_state"
    yawn_dir, no_yawn_dir = detect_yawn_folders(source)

    if yawn_dir is None or no_yawn_dir is None:
        print(
            f"Không tự dò được đủ 2 folder (yawn/no_yawn) trong {source}.\n"
            f"  Tìm thấy: yawn_dir={yawn_dir}, no_yawn_dir={no_yawn_dir}\n"
            "  Hãy tự kiểm tra tên thư mục thật rồi báo lại để chỉnh code."
        )
        return

    print(f"Yawn dataset: yawn_dir={yawn_dir}")
    print(f"              no_yawn_dir={no_yawn_dir}")

    counts = {"train": {"yawn": 0, "no_yawn": 0}, "val": {"yawn": 0, "no_yawn": 0}}

    for label, src_dir in [("yawn", yawn_dir), ("no_yawn", no_yawn_dir)]:
        images = sorted(list(src_dir.glob("*.jpg")) + list(src_dir.glob("*.png")))
        random.shuffle(images)
        n_val = max(1, int(len(images) * VAL_RATIO))
        val_images = set(images[:n_val])

        for img in tqdm(images, desc=f"Yawn: copying {label}"):
            split = "val" if img in val_images else "train"
            dst_dir = out_dir / split / label
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_path = dst_dir / img.name
            if not dry_run:
                shutil.copy2(img, dst_path)
            counts[split][label] += 1

    print(f"  TRAIN: yawn={counts['train']['yawn']}  no_yawn={counts['train']['no_yawn']}")
    print(f"  VAL:   yawn={counts['val']['yawn']}  no_yawn={counts['val']['no_yawn']}")
    if dry_run:
        print("  (--dry-run: chưa copy file thật)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mrl-source", help="Đường dẫn dataset MRL Eye đã tải (kagglehub path)")
    parser.add_argument("--yawn-source", help="Đường dẫn dataset Yawn đã tải (kagglehub path)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ xem trước, không copy file thật")
    args = parser.parse_args()

    if not args.mrl_source and not args.yawn_source:
        print("Cần ít nhất 1 trong 2: --mrl-source hoặc --yawn-source")
        return

    if args.mrl_source:
        prepare_mrl(Path(args.mrl_source), args.dry_run)
    if args.yawn_source:
        prepare_yawn(Path(args.yawn_source), args.dry_run)

    print(f"\nOutput tại: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()