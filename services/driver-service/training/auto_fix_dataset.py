"""One-shot auto-fix — no manual confirmation step.

Takes the runs already found by inspect_yawning.py (training/output/
yawning_runs.csv) and:
    1. Writes every image path in those runs into confirmed_delete.txt
       (overwrites any previous manual list).
    2. Calls review_mislabeled.py's phase_clean(mode="relabel") to
       build dataset/Multi class/train_cleaned/ — confirmed-bad
       yawning frames are moved into notdrowsy/ instead of dropped,
       so dataset size is preserved. Original dataset is untouched.
    3. Prints the same markdown report path so you can hand it to
       your instructor.

Prerequisite: you must have already run
    python training/inspect_yawning.py --min-run 20 --max-gap 5 --k -0.5
so that training/output/yawning_runs.csv exists.

Run (from driver-service root):
    python training/auto_fix_dataset.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_mislabeled import CONFIRM_PATH, phase_clean  # noqa: E402

# yawning_runs.csv is inspect_yawning.py's output, defined explicitly here.
YAWNING_RUNS_CSV = Path("training/output/yawning_runs.csv")


def main() -> None:
    if not YAWNING_RUNS_CSV.exists():
        print(
            f"Không tìm thấy {YAWNING_RUNS_CSV}. Hãy chạy trước:\n"
            "  python training/inspect_yawning.py --min-run 20 --max-gap 5 --k -0.5"
        )
        return

    runs_df = pd.read_csv(YAWNING_RUNS_CSV)
    all_paths: list[str] = []
    for cell in runs_df["all_img_paths"]:
        all_paths.extend(p for p in str(cell).split(";") if p)

    all_paths = sorted(set(all_paths))
    CONFIRM_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIRM_PATH.write_text("\n".join(all_paths), encoding="utf-8")
    print(f"Đã ghi {len(all_paths)} đường dẫn ảnh vào {CONFIRM_PATH}")

    print("Đang tạo dataset đã lọc (chế độ relabel — không mất dữ liệu)...")
    phase_clean(mode="relabel")

    print("\nHOÀN TẤT. Dataset gốc không bị thay đổi.")
    print("Dataset đã sửa: dataset/Multi class/train_cleaned/")
    print("Báo cáo: training/output/dataset_cleaning_report.md")


if __name__ == "__main__":
    main()