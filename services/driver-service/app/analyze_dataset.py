from pathlib import Path
from collections import Counter
from PIL import Image
from tqdm import tqdm

# =====================================================
# CONFIG
# =====================================================

# Đổi đường dẫn này nếu dataset của bạn nằm chỗ khác
DATASET_ROOT = Path(r"D:\multimodal-adas\services\driver-service\dataset\Multi class")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

# =====================================================
# HELPER
# =====================================================

def is_image(path: Path):
    return path.suffix.lower() in IMAGE_EXTS


def count_images(folder: Path):
    return sum(
        1 for p in folder.rglob("*")
        if p.is_file() and is_image(p)
    )


# =====================================================
# FIND SPLITS
# =====================================================

print("=" * 60)
print("DATASET ANALYSIS")
print("=" * 60)

splits = []

for name in ["train", "val", "validation", "test"]:
    p = DATASET_ROOT / name
    if p.exists():
        splits.append(name)

if not splits:
    print("❌ Không tìm thấy train / val / test")
    exit()

print("\nFound splits:")

for s in splits:
    print(f"  ✔ {s}")

# =====================================================
# COLLECT IMAGE LIST
# =====================================================

image_paths = []

for split in splits:
    split_dir = DATASET_ROOT / split

    for p in split_dir.rglob("*"):
        if p.is_file() and is_image(p):
            image_paths.append(p)

print(f"\nTotal image files found : {len(image_paths):,}")

# =====================================================
# ANALYSIS
# =====================================================

class_counter = Counter()
merged_counter = Counter()

subjects = Counter()

glasses_counter = Counter()

image_sizes = Counter()

bad_images = []

for img_path in tqdm(image_paths, desc="Scanning"):

    cls = img_path.parent.name

    class_counter[cls] += 1

    if cls == "notdrowsy":
        merged_counter["notdrowsy"] += 1
    else:
        merged_counter["drowsy"] += 1

    name = img_path.stem.lower()

    parts = name.split("_")

    if len(parts):
        subjects[parts[0]] += 1

    if "noglasses" in name:
        glasses_counter["No Glasses"] += 1
    elif "glasses" in name:
        glasses_counter["Glasses"] += 1

    try:
        with Image.open(img_path) as img:
            image_sizes[img.size] += 1
    except:
        bad_images.append(img_path)

# =====================================================
# REPORT
# =====================================================

print("\n")
print("=" * 60)
print("SUMMARY")
print("=" * 60)

print(f"Total Images : {len(image_paths):,}")

print("\nSplit Statistics")

for split in splits:
    n = count_images(DATASET_ROOT / split)
    print(f"{split:<12}: {n:,}")

print("\nClass Distribution")
print("-" * 40)

for cls, num in sorted(class_counter.items()):
    print(f"{cls:<30}{num:>8,}")

print("\nMerged Distribution")
print("-" * 40)

total = sum(merged_counter.values())

for cls, num in merged_counter.items():
    pct = num / total * 100
    print(f"{cls:<15}{num:>8,} ({pct:.2f}%)")

print("\nBalance Check")
print("-" * 40)

if len(merged_counter) == 2:
    a = merged_counter["drowsy"]
    b = merged_counter["notdrowsy"]

    ratio = max(a, b) / min(a, b)

    if ratio < 1.2:
        print("✅ Dataset khá cân bằng")
    elif ratio < 2:
        print("⚠ Dataset hơi lệch")
    else:
        print("❌ Dataset mất cân bằng")

print("\nSubjects")
print("-" * 40)

print("Unique Subjects :", len(subjects))

print("\nTop 10 Subjects")

for sid, num in subjects.most_common(10):
    print(f"{sid:<10}{num}")

print("\nGlasses Distribution")
print("-" * 40)

for k, v in glasses_counter.items():
    print(f"{k:<15}{v}")

print("\nImage Sizes")
print("-" * 40)

for size, num in image_sizes.most_common(10):
    print(f"{str(size):<20}{num}")

print("\nBad Images")
print("-" * 40)

print(len(bad_images))

if bad_images:
    print("\nFirst bad image:")
    print(bad_images[0])

print("\n")
print("=" * 60)
print("RECOMMENDATION")
print("=" * 60)

if "val" not in splits and "validation" not in splits:
    print("❌ Chưa có Validation Set")

if "test" not in splits:
    print("❌ Chưa có Test Set")

if "val" in splits or "validation" in splits:
    print("✅ Validation Set OK")

if "test" in splits:
    print("✅ Test Set OK")

print("\nDone.")