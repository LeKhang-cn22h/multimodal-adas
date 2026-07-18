"""Inspect MRL Eye Dataset + Yawn Dataset — structure, existing
train/test/val split (if any), label distribution, image counts,
resolution sample. Read-only, doesn't copy/move anything.

Run:
    python training/inspect_new_datasets.py ^
        --mrl-source "C:\\Users\\Acer\\.cache\\kagglehub\\datasets\\tauilabdelilah\\mrl-eye-dataset\\versions\\6" ^
        --yawn-source "C:\\Users\\Acer\\.cache\\kagglehub\\datasets\\davidvazquezcic\\yawn-dataset\\versions\\1"
"""

import argparse
from collections import Counter
from pathlib import Path

import cv2

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
SPLIT_KEYWORDS = {"train": "train", "test": "test", "val": "val", "valid": "val", "validation": "val"}


def find_leaf_image_dirs(root: Path) -> list[Path]:
    """Any directory that directly contains >=1 image file."""
    leaves = []
    for d in sorted({p.parent for p in root.rglob("*") if p.suffix.lower() in IMG_EXTS}):
        leaves.append(d)
    return leaves


def guess_split(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    for part in rel.parts:
        key = part.lower()
        for kw, split_name in SPLIT_KEYWORDS.items():
            if kw in key:
                return split_name
    return "(chưa chia — flat)"


def sample_resolution(files: list[Path], n: int = 20) -> tuple[int, int, int, int] | None:
    """Return (min_w, max_w, min_h, max_h) from a sample of files."""
    widths, heights = [], []
    for f in files[:n]:
        img = cv2.imread(str(f))
        if img is None:
            continue
        h, w = img.shape[:2]
        widths.append(w)
        heights.append(h)
    if not widths:
        return None
    return min(widths), max(widths), min(heights), max(heights)


# =========================================================================
# MRL Eye Dataset
# =========================================================================


def inspect_mrl(source: Path) -> None:
    print("\n" + "=" * 70)
    print("MRL EYE DATASET")
    print("=" * 70)

    if not source.is_dir():
        print(f"Lỗi: không tìm thấy thư mục: {source}")
        return

    leaf_dirs = find_leaf_image_dirs(source)
    print(f"Số thư mục con chứa ảnh trực tiếp: {len(leaf_dirs)}")
    for d in leaf_dirs[:10]:
        n = sum(1 for _ in d.glob("*") if _.suffix.lower() in IMG_EXTS)
        print(f"  {d.relative_to(source)}  ({n} ảnh)  split={guess_split(d, source)}")
    if len(leaf_dirs) > 10:
        print(f"  ... và {len(leaf_dirs) - 10} thư mục khác")

    all_files = [p for p in source.rglob("*") if p.suffix.lower() in IMG_EXTS]
    print(f"\nTổng số ảnh: {len(all_files)}")

    # ── Parse filenames (label is IN the filename, not the folder) ──
    parsed, unparsed = 0, 0
    eye_state_counter = Counter()
    gender_counter = Counter()
    glasses_counter = Counter()
    reflections_counter = Counter()
    lighting_counter = Counter()
    sensor_counter = Counter()
    subjects = set()

    for f in all_files:
        parts = f.stem.split("_")
        if len(parts) < 8:
            unparsed += 1
            continue
        try:
            subject, _img_id, gender, glasses, eye_state, reflections, lighting, sensor = parts[:8]
            subjects.add(subject)
            eye_state_counter[eye_state] += 1
            gender_counter[gender] += 1
            glasses_counter[glasses] += 1
            reflections_counter[reflections] += 1
            lighting_counter[lighting] += 1
            sensor_counter[sensor] += 1
            parsed += 1
        except ValueError:
            unparsed += 1

    print(f"Parse tên file thành công: {parsed}  |  Không parse được: {unparsed}")
    print(f"Số subject (người) khác nhau: {len(subjects)}")
    print(f"\nNhãn eye_state (0=closed, 1=open):")
    for k, v in sorted(eye_state_counter.items()):
        label = {"0": "closed", "1": "open"}.get(k, f"unknown({k})")
        print(f"  {label}: {v}  ({v/parsed*100:.1f}%)")

    print(f"\nGender (0=man, 1=woman): {dict(gender_counter)}")
    print(f"Glasses (0=no, 1=yes): {dict(glasses_counter)}")
    print(f"Reflections (0=none,1=small,2=big): {dict(reflections_counter)}")
    print(f"Lighting (0=bad, 1=good): {dict(lighting_counter)}")
    print(f"Sensor (01=RealSense,02=IDS,03=Aptina): {dict(sensor_counter)}")

    res = sample_resolution(all_files)
    if res:
        min_w, max_w, min_h, max_h = res
        print(f"\nĐộ phân giải (mẫu 20 ảnh): W {min_w}-{max_w}px, H {min_h}-{max_h}px")

    has_split = any(guess_split(d, source) != "(chưa chia — flat)" for d in leaf_dirs)
    print(f"\n>> Dataset đã có sẵn train/test/val split trong tên thư mục? {'CÓ' if has_split else 'CHƯA — cần tự chia'}")
    if not has_split:
        print(
            ">> Khuyến nghị: dùng training/prepare_cnn_datasets.py để tự chia "
            "TRAIN/VAL theo SUBJECT (không chia ngẫu nhiên theo ảnh, tránh cùng "
            "1 người xuất hiện ở cả 2 tập)."
        )


# =========================================================================
# Yawn Dataset
# =========================================================================


def inspect_yawn(source: Path) -> None:
    print("\n" + "=" * 70)
    print("YAWN DATASET")
    print("=" * 70)

    if not source.is_dir():
        print(f"Lỗi: không tìm thấy thư mục: {source}")
        return

    leaf_dirs = find_leaf_image_dirs(source)
    print(f"Số thư mục con chứa ảnh trực tiếp: {len(leaf_dirs)}")

    total_by_label_split: dict[tuple[str, str], int] = Counter()
    all_sample_files: list[Path] = []

    for d in leaf_dirs:
        files = [p for p in d.glob("*") if p.suffix.lower() in IMG_EXTS]
        n = len(files)
        split = guess_split(d, source)
        name = d.name.lower()
        if "no" in name and "yawn" in name:
            label = "no_yawn"
        elif "yawn" in name:
            label = "yawn"
        elif "close" in name:
            label = "closed_eye(?)"
        elif "open" in name:
            label = "open_eye(?)"
        else:
            label = f"unknown({d.name})"

        total_by_label_split[(split, label)] += n
        print(f"  {d.relative_to(source)}  ({n} ảnh)  ->  split={split}  label={label}")
        all_sample_files.extend(files[:5])

    print("\nTổng hợp theo (split, label):")
    grand_total = 0
    for (split, label), n in sorted(total_by_label_split.items()):
        print(f"  split={split:20s}  label={label:20s}  n={n}")
        grand_total += n
    print(f"\nTổng số ảnh: {grand_total}")

    res = sample_resolution(all_sample_files)
    if res:
        min_w, max_w, min_h, max_h = res
        print(f"Độ phân giải (mẫu): W {min_w}-{max_w}px, H {min_h}-{max_h}px")

    has_split = any(s != "(chưa chia — flat)" for (s, _l) in total_by_label_split)
    print(f"\n>> Dataset đã có sẵn train/test/val split? {'CÓ' if has_split else 'CHƯA — cần tự chia'}")
    if not has_split:
        print(
            ">> Khuyến nghị: dùng training/prepare_cnn_datasets.py để tự chia "
            "TRAIN/VAL (80/20 ngẫu nhiên, vì dataset này không có subject_id)."
        )
    else:
        print(
            ">> Đã có split sẵn — hãy đối chiếu với training/prepare_cnn_datasets.py, "
            "có thể cần chỉnh code để dùng đúng split có sẵn thay vì tự chia lại."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mrl-source", help="Đường dẫn MRL Eye Dataset")
    parser.add_argument("--yawn-source", help="Đường dẫn Yawn Dataset")
    args = parser.parse_args()

    if not args.mrl_source and not args.yawn_source:
        print("Cần ít nhất 1 trong 2: --mrl-source hoặc --yawn-source")
        return

    if args.mrl_source:
        inspect_mrl(Path(args.mrl_source))
    if args.yawn_source:
        inspect_yawn(Path(args.yawn_source))


if __name__ == "__main__":
    main()