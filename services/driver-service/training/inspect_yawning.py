"""Inspect yawning/ in depth — find CONTIGUOUS runs of frames whose
mouth looks closed/normal (alert-like MAR) inside videos labeled
'yawning'.

Why runs, not single frames:
    A single frame with high suspicion score could just be noise
    (landmark jitter, mid-yawn transition). But if 20-30 CONSECUTIVE
    frames (i.e. ~0.5-1 second of continuous video) all look alert,
    that is very strong evidence of a mislabeled segment — the person
    simply wasn't yawning during that stretch, yet every frame in it
    was inherited the video-level 'yawning' label.

Uses the already-generated training/output/mislabel_review.csv (no
need to touch images again — fast).

Output:
    training/output/yawning_runs.csv         - one row per suspicious run
    training/output/yawning_timelines/       - one MAR-vs-frame plot per
                                                subject, suspicious runs
                                                shaded in red
    training/output/yawning_run_review/      - contact sheets sampling
                                                frames from each run, for
                                                fast visual confirmation

Run:
    python training/inspect_yawning.py
    python training/inspect_yawning.py --min-run 20 --max-gap 5 --k 0.0
"""

import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

matplotlib.use("Agg")

CSV_PATH = Path("training/output/mislabel_review.csv")
OUTPUT_DIR = Path("training/output")
TIMELINE_DIR = OUTPUT_DIR / "yawning_timelines"
RUN_REVIEW_DIR = OUTPUT_DIR / "yawning_run_review"
RUNS_CSV = OUTPUT_DIR / "yawning_runs.csv"

# Baseline computed by review_mislabeled.py's last run (printed in its
# log as "Alert baseline: EAR=... MAR=..."). Update these two numbers
# if you re-run the baseline scan and get different values.
BASELINE_MAR_MEAN = 0.2271
BASELINE_MAR_STD = 0.1150

THUMB_SIZE = 140
GRID_COLS = 5
SAMPLES_PER_RUN = 10  # max frames sampled from each run for contact sheet


def find_runs(sub_df: pd.DataFrame, mar_threshold: float, min_run: int, max_gap: int) -> list[dict]:
    """sub_df: rows for ONE subject, already sorted by frame_number."""
    runs = []
    current = []

    def flush():
        if len(current) >= min_run:
            frames = [r["frame_number"] for r in current]
            mars = [r["mar"] for r in current]
            runs.append({
                "start_frame": frames[0],
                "end_frame": frames[-1],
                "length": len(current),
                "avg_mar": sum(mars) / len(mars),
                "rows": list(current),
            })

    prev_frame = None
    for _, row in sub_df.iterrows():
        is_alert_like = row["mar"] <= mar_threshold
        if not is_alert_like:
            flush()
            current = []
            prev_frame = row["frame_number"]
            continue

        if prev_frame is not None and (row["frame_number"] - prev_frame) > max_gap:
            # gap too big -> treat as a new run, close the old one
            flush()
            current = []

        current.append(row)
        prev_frame = row["frame_number"]

    flush()
    return runs


def build_contact_sheet(image_paths: list[Path], out_path: Path) -> None:
    if not image_paths:
        return
    n = len(image_paths)
    cols = min(GRID_COLS, n)
    rows = (n + cols - 1) // cols
    cell_h = THUMB_SIZE + 22
    sheet = Image.new("RGB", (cols * THUMB_SIZE, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for i, path in enumerate(image_paths):
        row, col = divmod(i, cols)
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((THUMB_SIZE, THUMB_SIZE))
        except Exception:
            continue
        x, y = col * THUMB_SIZE, row * cell_h
        sheet.paste(img, (x, y))
        draw.text((x + 2, y + THUMB_SIZE + 2), path.stem[-28:], fill="black", font=font)

    sheet.save(out_path, quality=90)


def plot_timeline(subject_id: str, sub_df: pd.DataFrame, runs: list[dict], mar_threshold: float) -> None:
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(sub_df["frame_number"], sub_df["mar"], color="steelblue", linewidth=0.8, label="MAR")
    ax.axhline(mar_threshold, color="gray", linestyle="--", linewidth=1,
                label=f"Ngưỡng nghi ngờ (alert-like) = {mar_threshold:.3f}")

    for run in runs:
        ax.axvspan(run["start_frame"], run["end_frame"], color="red", alpha=0.25)

    ax.set_title(f"Subject {subject_id} — yawning scenario — MAR theo frame")
    ax.set_xlabel("frame_number")
    ax.set_ylabel("MAR")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(TIMELINE_DIR / f"subject_{subject_id}_mar_timeline.png", dpi=130)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-run", type=int, default=20,
                         help="Số frame liên tiếp tối thiểu để coi là 1 đoạn nghi ngờ (default 20 ~ 0.6-0.7s @30fps)")
    parser.add_argument("--max-gap", type=int, default=5,
                         help="Khoảng cách frame_number tối đa vẫn coi là liên tục (bù cho frame bị skip do không detect được mặt)")
    parser.add_argument("--k", type=float, default=0.0,
                         help="Ngưỡng = baseline_mar_mean + k * baseline_mar_std. k=0 nghĩa là MAR <= trung bình người tỉnh táo")
    args = parser.parse_args()

    mar_threshold = BASELINE_MAR_MEAN + args.k * BASELINE_MAR_STD

    TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
    RUN_REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(CSV_PATH)
    df = df[df["scenario"] == "yawning"].copy()
    print(f"Tổng ảnh yawning: {len(df)}")
    print(f"Ngưỡng MAR coi là 'giống người tỉnh táo': {mar_threshold:.4f}")
    print(f"min_run={args.min_run} frame, max_gap={args.max_gap} frame\n")

    all_runs = []
    for subject_id in sorted(df["subject_id"].unique()):
        sub_df = df[df["subject_id"] == subject_id].sort_values("frame_number")
        runs = find_runs(sub_df, mar_threshold, args.min_run, args.max_gap)
        if not runs:
            continue

        plot_timeline(str(subject_id), sub_df, runs, mar_threshold)

        subject_dir = RUN_REVIEW_DIR / f"subject_{subject_id}"
        subject_dir.mkdir(parents=True, exist_ok=True)

        for i, run in enumerate(runs):
            rows = run["rows"]
            # sample up to SAMPLES_PER_RUN frames evenly across the run
            step = max(1, len(rows) // SAMPLES_PER_RUN)
            sampled = rows[::step][:SAMPLES_PER_RUN]
            sample_paths = [Path(r["img_path"]) for r in sampled]

            sheet_path = subject_dir / f"run{i:02d}_frames{run['start_frame']}-{run['end_frame']}_len{run['length']}.jpg"
            build_contact_sheet(sample_paths, sheet_path)

            all_runs.append({
                "subject_id": subject_id,
                "run_index": i,
                "start_frame": run["start_frame"],
                "end_frame": run["end_frame"],
                "length": run["length"],
                "avg_mar": round(run["avg_mar"], 4),
                "all_img_paths": ";".join(str(r["img_path"]) for r in rows),
                "contact_sheet": str(sheet_path),
            })

    if not all_runs:
        print("Không tìm thấy đoạn (run) nghi ngờ nào với tham số hiện tại.")
        print("Thử giảm --min-run hoặc tăng --k để nới lỏng điều kiện.")
        return

    runs_df = pd.DataFrame(all_runs).sort_values("length", ascending=False)
    runs_df.to_csv(RUNS_CSV, index=False)

    total_frames_in_runs = runs_df["length"].sum()
    print("=" * 70)
    print(f"Tìm thấy {len(runs_df)} đoạn nghi ngờ, tổng {total_frames_in_runs} frame")
    print(f"({total_frames_in_runs/len(df)*100:.2f}% tổng số ảnh yawning)")
    print(f"\nTop 10 đoạn dài nhất (khả năng sai cao nhất):")
    print(runs_df[["subject_id", "start_frame", "end_frame", "length", "avg_mar"]].head(10).to_string(index=False))
    print(f"\nChi tiết đầy đủ: {RUNS_CSV}")
    print(f"Timeline (đồ thị MAR theo frame, đoạn nghi ngờ tô đỏ): {TIMELINE_DIR}")
    print(f"Contact sheet theo từng đoạn: {RUN_REVIEW_DIR}")
    print("=" * 70)
    print(
        "\nCách dùng tiếp:\n"
        "1. Mở vài file trong yawning_timelines/ để xem tổng quan — đoạn tô\n"
        "   đỏ càng dài, càng chắc chắn là bị gán nhãn sai kéo dài.\n"
        "2. Với mỗi đoạn nghi ngờ, mở contact sheet tương ứng trong\n"
        "   yawning_run_review/subject_XXX/ để xác nhận bằng mắt.\n"
        "3. Đoạn nào xác nhận đúng là sai -> mở yawning_runs.csv, lấy cột\n"
        "   'all_img_paths' (các path cách nhau bởi ';'), tách ra và thêm\n"
        "   TỪNG dòng vào training/output/confirmed_delete.txt.\n"
        "4. Sau đó chạy: python training/review_mislabeled.py --clean"
    )


if __name__ == "__main__":
    main()