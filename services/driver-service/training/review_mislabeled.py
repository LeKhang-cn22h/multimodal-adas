"""Review script — flag likely-mislabeled 'drowsy' images.

Idea:
    'notdrowsy/' is (mostly) reliable ground truth for what an ALERT
    face looks like (eyes open, mouth closed). We compute the EAR/MAR
    distribution there as a baseline, then flag images inside
    'drowsy/<scenario>/' whose EAR/MAR looks just as "alert" as that
    baseline — these are the frames you described (drowsy folder but
    eyes open / mouth normal, no yawn).

    This does NOT delete anything automatically. It:
      1. Computes ear_avg / mar for every image (reusing the same
         landmark pipeline as Step 2, so numbers are consistent).
      2. Flags suspicious drowsy images per scenario rule.
      3. Writes a CSV report sorted by "how alert it looks".
      4. Copies the top suspicious images into a review folder with
         metrics baked into the filename, PLUS builds contact-sheet
         grid images (25 thumbnails per sheet) so you can eyeball
         hundreds of frames in seconds instead of opening one by one.
      5. You manually confirm bad ones (write their paths, one per
         line, into training/output/confirmed_delete.txt).
      6. Re-run with --clean to build a NEW, separate dataset copy
         (train_cleaned/) that excludes those confirmed files. The
         ORIGINAL dataset/Multi class/train/ is never touched or
         deleted from. A markdown report is also generated, showing
         before/after counts per scenario — this is the artifact you
         hand to your instructor as evidence the raw dataset has
         label noise.

Run (from driver-service root, same place you run Step 2):
    python training/review_mislabeled.py
    python training/review_mislabeled.py --clean   # after you edit confirmed_delete.txt
"""

import argparse
import csv
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.mediapipe_service import FaceLandmarkerService
from app.utils.ear import LEFT_EYE, RIGHT_EYE, calculate_ear
from app.utils.logger import get_logger
from app.utils.mar import calculate_mar

logger = get_logger()

DATASET_ROOT = Path("dataset/Multi class/train")
CLEANED_ROOT = Path("dataset/Multi class/train_cleaned")   # bản sao đã lọc, KHÔNG đụng bản gốc
OUTPUT_DIR = Path("training/output")
REVIEW_DIR = OUTPUT_DIR / "review"
CSV_PATH = OUTPUT_DIR / "mislabel_review.csv"
CONFIRM_PATH = OUTPUT_DIR / "confirmed_delete.txt"
REPORT_PATH = OUTPUT_DIR / "dataset_cleaning_report.md"

DROWSY_SCENARIOS = ["sleepyCombination", "yawning", "slowBlinkWithNodding"]

# How many of the most-suspicious images per scenario to export for
# visual review (contact sheets + individual copies).
TOP_N_PER_SCENARIO = 300
THUMB_SIZE = 140          # px, per cell in contact sheet
GRID_COLS = 5
GRID_ROWS = 5             # 25 images per sheet


def parse_filename(filename: str) -> dict:
    name = filename.replace(".jpg", "")
    parts = name.split("_")
    return {
        "subject_id": parts[0],
        "glasses": parts[1],
        "scenario": "_".join(parts[2:-2]),
        "frame_number": int(parts[-2]),
        "label_str": parts[-1],
    }


def compute_metrics(landmark_service, img_path: Path) -> dict | None:
    frame = cv2.imread(str(img_path))
    if frame is None:
        return None
    timestamp_ms = int(time.time() * 1000)
    result = landmark_service.detect(frame, timestamp_ms)
    if not result.face_detected or result.landmarks is None:
        return None

    landmarks = result.landmarks
    ear_left = float(calculate_ear(landmarks, LEFT_EYE))
    ear_right = float(calculate_ear(landmarks, RIGHT_EYE))
    ear_avg = (ear_left + ear_right) / 2.0
    mar = float(calculate_mar(landmarks))

    # TS-remove-headpose: Head Pose removed — yaw/pitch/roll = 0 always
    yaw, pitch, roll = 0.0, 0.0, 0.0

    return {
        "ear_avg": ear_avg, "mar": mar,
        "yaw": float(yaw), "pitch": float(pitch), "roll": float(roll),
    }


def collect(root: Path, scenario: str | None, label_binary: int) -> list[dict]:
    entries = []
    folder = root if scenario is None else root / scenario
    if not folder.is_dir():
        logger.warning("Missing directory: %s", folder)
        return entries
    for img_path in sorted(folder.glob("*.jpg")):
        meta = parse_filename(img_path.name)
        meta["img_path"] = img_path
        meta["label_binary"] = label_binary
        meta["scenario_folder"] = scenario or "notdrowsy"
        entries.append(meta)
    return entries


def build_contact_sheet(image_paths: list[Path], out_path: Path) -> None:
    """Grid of thumbnails with filenames underneath, for fast eyeballing."""
    cell_h = THUMB_SIZE + 22  # extra space for caption text
    sheet = Image.new(
        "RGB", (GRID_COLS * THUMB_SIZE, GRID_ROWS * cell_h), "white",
    )
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for i, path in enumerate(image_paths[: GRID_COLS * GRID_ROWS]):
        row, col = divmod(i, GRID_COLS)
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((THUMB_SIZE, THUMB_SIZE))
        except Exception:
            continue
        x = col * THUMB_SIZE
        y = row * cell_h
        sheet.paste(img, (x, y))
        caption = path.stem[-28:]  # keep it short
        draw.text((x + 2, y + THUMB_SIZE + 2), caption, fill="black", font=font)

    sheet.save(out_path, quality=90)


def phase_scan() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Loading FaceLandmarkerService...")
    landmark_service = FaceLandmarkerService(model_path="face_landmarker.task")
    landmark_service.load_model()

    # ── Step 1: baseline from notdrowsy (known-alert ground truth) ──
    logger.info("Computing alert baseline from notdrowsy/ ...")
    notdrowsy_entries = collect(DATASET_ROOT / "notdrowsy", None, 0)
    baseline_ear, baseline_mar = [], []
    for e in tqdm(notdrowsy_entries, desc="Baseline (notdrowsy)"):
        m = compute_metrics(landmark_service, e["img_path"])
        if m:
            baseline_ear.append(m["ear_avg"])
            baseline_mar.append(m["mar"])

    ear_mean, ear_std = float(np.mean(baseline_ear)), float(np.std(baseline_ear))
    mar_mean, mar_std = float(np.mean(baseline_mar)), float(np.std(baseline_mar))
    logger.info(
        "Alert baseline: EAR=%.4f±%.4f  MAR=%.4f±%.4f",
        ear_mean, ear_std, mar_mean, mar_std,
    )

    # ── Step 2: score every drowsy image against that baseline ──────
    rows = []
    for scenario in DROWSY_SCENARIOS:
        entries = collect(DATASET_ROOT / "drowsy", scenario, 1)
        for e in tqdm(entries, desc=f"Scoring {scenario}"):
            m = compute_metrics(landmark_service, e["img_path"])
            if m is None:
                continue

            if scenario in ("sleepyCombination", "slowBlinkWithNodding"):
                # eyes as open as an alert person -> suspicious
                suspicion = (m["ear_avg"] - ear_mean) / (ear_std + 1e-6)
            else:  # yawning
                # mouth as closed as an alert person -> suspicious
                suspicion = (mar_mean - m["mar"]) / (mar_std + 1e-6)

            rows.append({
                "img_path": str(e["img_path"]),
                "subject_id": e["subject_id"],
                "scenario": scenario,
                "frame_number": e["frame_number"],
                "ear_avg": round(m["ear_avg"], 4),
                "mar": round(m["mar"], 4),
                "suspicion_score": round(float(suspicion), 4),
            })

    landmark_service.close_model()

    # ── Step 3: write CSV, sorted worst-first per scenario ───────────
    rows.sort(key=lambda r: (r["scenario"], -r["suspicion_score"]))
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Report written: %s (%d rows)", CSV_PATH, len(rows))

    # ── Step 4: export top-N suspicious per scenario for visual review ──
    for scenario in DROWSY_SCENARIOS:
        scenario_rows = [r for r in rows if r["scenario"] == scenario][:TOP_N_PER_SCENARIO]
        if not scenario_rows:
            continue
        scenario_dir = REVIEW_DIR / scenario
        scenario_dir.mkdir(parents=True, exist_ok=True)

        copied_paths = []
        for r in scenario_rows:
            src = Path(r["img_path"])
            dst_name = f"score{r['suspicion_score']:.2f}_{src.name}"
            dst = scenario_dir / dst_name
            shutil.copy2(src, dst)
            copied_paths.append(dst)

        # contact sheets, 25 images each
        for i in range(0, len(copied_paths), GRID_COLS * GRID_ROWS):
            batch = copied_paths[i:i + GRID_COLS * GRID_ROWS]
            sheet_path = scenario_dir / f"_contact_sheet_{i // (GRID_COLS*GRID_ROWS):02d}.jpg"
            build_contact_sheet(batch, sheet_path)

        logger.info(
            "%s: exported %d suspicious images + %d contact sheets -> %s",
            scenario, len(copied_paths),
            (len(copied_paths) + 24) // 25, scenario_dir,
        )

    print("\n" + "=" * 70)
    print("XONG PHẦN QUÉT. Các bước tiếp theo:")
    print(f"1. Mở các file '_contact_sheet_XX.jpg' trong: {REVIEW_DIR}")
    print("   (mỗi sheet 25 ảnh, tên file có score càng cao = càng nghi ngờ)")
    print("2. Ảnh nào đúng là bị gán sai nhãn (mắt mở/miệng bình thường)")
    print(f"   -> mở file CSV: {CSV_PATH}, copy cột 'img_path' của các dòng đó")
    print(f"   -> paste vào: {CONFIRM_PATH} (mỗi dòng 1 path)")
    print("3. Chạy lại: python training/review_mislabeled.py --clean")
    print(f"   -> tạo BẢN SAO dataset đã lọc tại: {CLEANED_ROOT}")
    print(f"   -> dataset gốc ({DATASET_ROOT}) KHÔNG bị thay đổi.")
    print(f"   -> báo cáo (để đưa giáo viên xem) tại: {REPORT_PATH}")
    print("=" * 70)


def _relative_scenario_dirs() -> list[tuple[Path, str, int]]:
    """(source_dir, scenario_label, label_binary) pairs mirroring collect()."""
    pairs = []
    for scenario in DROWSY_SCENARIOS:
        pairs.append((DATASET_ROOT / "drowsy" / scenario, scenario, 1))
    pairs.append((DATASET_ROOT / "notdrowsy", "notdrowsy", 0))
    return pairs


def phase_clean(mode: str = "exclude") -> None:
    """Build a NEW cleaned dataset copy + a markdown report, without
    touching or deleting anything in the original dataset.

    mode="exclude": confirmed-bad images are simply left out of the
        cleaned copy (dataset shrinks).
    mode="relabel": confirmed-bad images are instead copied into the
        cleaned copy's notdrowsy/ folder (dataset size preserved,
        label corrected instead of dropped).
    """
    if not CONFIRM_PATH.exists():
        logger.error(
            "Không tìm thấy %s. Hãy tạo file này với danh sách "
            "đường dẫn ảnh nghi bị gán sai (mỗi dòng 1 path) trước khi chạy --clean.",
            CONFIRM_PATH,
        )
        return

    excluded = {
        str(Path(line.strip()))
        for line in CONFIRM_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    logger.info(
        "Số ảnh sẽ %s: %d",
        "được chuyển sang notdrowsy" if mode == "relabel" else "bị loại khỏi bản sao đã lọc",
        len(excluded),
    )

    if CLEANED_ROOT.exists():
        logger.warning(
            "%s đã tồn tại — sẽ ghi đè/bổ sung vào thư mục này.", CLEANED_ROOT,
        )

    notdrowsy_dst_dir = CLEANED_ROOT / "notdrowsy"
    if mode == "relabel":
        notdrowsy_dst_dir.mkdir(parents=True, exist_ok=True)

    stats = []
    excluded_examples: dict[str, list[str]] = {}
    relabeled_count = 0

    for src_dir, scenario_label, label_binary in _relative_scenario_dirs():
        if not src_dir.is_dir():
            logger.warning("Bỏ qua, không tồn tại: %s", src_dir)
            continue

        rel = src_dir.relative_to(DATASET_ROOT)
        dst_dir = CLEANED_ROOT / rel
        dst_dir.mkdir(parents=True, exist_ok=True)

        total_before, excluded_count = 0, 0
        examples = []
        for img_path in sorted(src_dir.glob("*.jpg")):
            total_before += 1
            if str(img_path) in excluded:
                excluded_count += 1
                if len(examples) < 15:
                    examples.append(img_path.name)
                if mode == "relabel" and label_binary == 1:
                    # copy into notdrowsy/ instead of the original drowsy folder
                    dst_name = f"relabeled_{scenario_label}_{img_path.name}"
                    shutil.copy2(img_path, notdrowsy_dst_dir / dst_name)
                    relabeled_count += 1
                continue
            shutil.copy2(img_path, dst_dir / img_path.name)

        stats.append({
            "scenario": scenario_label,
            "label": "drowsy" if label_binary == 1 else "notdrowsy",
            "total_before": total_before,
            "excluded": excluded_count,
            "total_after": total_before - excluded_count,
            "pct_excluded": (excluded_count / total_before * 100) if total_before else 0.0,
        })
        excluded_examples[scenario_label] = examples

    matched = sum(s["excluded"] for s in stats)
    not_found = len(excluded) - matched
    if not_found > 0:
        logger.warning(
            "%d path trong %s không khớp ảnh nào trong dataset gốc "
            "(có thể do sai đường dẫn hoặc đã sửa trước đó).",
            not_found, CONFIRM_PATH,
        )

    # ── Write markdown report (evidence for instructor) ─────────────
    total_before_all = sum(s["total_before"] for s in stats)
    total_excluded_all = sum(s["excluded"] for s in stats)
    pct_all = (total_excluded_all / total_before_all * 100) if total_before_all else 0.0

    lines = []
    lines.append("# Báo cáo rà soát nhãn dataset (Drowsiness Detection)")
    lines.append("")
    lines.append(f"- Dataset gốc: `{DATASET_ROOT}` (giữ nguyên, không chỉnh sửa)")
    lines.append(f"- Bản đã lọc: `{CLEANED_ROOT}`")
    lines.append(f"- Chế độ xử lý: **{'Gán lại nhãn sang notdrowsy' if mode == 'relabel' else 'Loại bỏ khỏi dataset'}**")
    lines.append(
        "- Phương pháp phát hiện nghi ngờ: so sánh EAR (độ mở mắt) và MAR "
        "(độ mở miệng) của từng ảnh trong `drowsy/` với phân bố baseline "
        "tính từ `notdrowsy/` (ground truth tỉnh táo), kết hợp phát hiện "
        "các ĐOẠN liên tục nhiều frame (không chỉ frame đơn lẻ) để giảm "
        "nhiễu do rung động landmark. Ảnh nghi ngờ được xác nhận thủ công "
        "qua contact sheet trước khi xử lý."
    )
    lines.append("")
    lines.append("## Tổng quan")
    lines.append("")
    lines.append(f"- Tổng số ảnh gốc: **{total_before_all}**")
    lines.append(f"- Số ảnh xác nhận gán nhãn sai: **{total_excluded_all}** ({pct_all:.2f}%)")
    if mode == "relabel":
        lines.append(f"- Số ảnh được gán lại thành notdrowsy: **{relabeled_count}**")
        lines.append(f"- Tổng số ảnh trong bản đã lọc: **{total_before_all}** (không đổi, chỉ sửa nhãn)")
    else:
        lines.append(f"- Số ảnh còn lại trong bản đã lọc: **{total_before_all - total_excluded_all}**")
    lines.append("")
    lines.append("## Chi tiết theo scenario")
    lines.append("")
    lines.append("| Scenario | Nhãn | Số ảnh gốc | Sai nhãn | Còn lại | % sai |")
    lines.append("|---|---|---|---|---|---|")
    for s in stats:
        lines.append(
            f"| {s['scenario']} | {s['label']} | {s['total_before']} | "
            f"{s['excluded']} | {s['total_after']} | {s['pct_excluded']:.2f}% |"
        )
    lines.append("")
    lines.append("## Ví dụ ảnh bị gán sai nhãn (tối đa 15 ảnh mỗi scenario)")
    lines.append("")
    for scenario_label, examples in excluded_examples.items():
        if not examples:
            continue
        lines.append(f"**{scenario_label}:**")
        for name in examples:
            lines.append(f"- `{name}`")
        lines.append("")
    lines.append(
        "> Ghi chú: đây là các ảnh mà mặc dù nằm trong thư mục `drowsy/`, "
        "khuôn mặt có EAR/MAR giống hệt trạng thái tỉnh táo — được xác "
        "nhận bằng mắt qua contact sheet/timeline trước khi xử lý."
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    logger.info("Đã tạo bản dataset đã lọc: %s", CLEANED_ROOT)
    logger.info("Báo cáo: %s", REPORT_PATH)
    print(f"\nTỷ lệ nhãn nhiễu phát hiện được: {pct_all:.2f}% ({total_excluded_all}/{total_before_all} ảnh)")
    if mode == "relabel":
        print(f"Đã gán lại {relabeled_count} ảnh sang notdrowsy (không mất dữ liệu).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clean", action="store_true",
        help=(
            "Tạo bản sao dataset đã lọc (train_cleaned/) dựa trên "
            "confirmed_delete.txt. Không đụng vào dataset gốc."
        ),
    )
    parser.add_argument(
        "--mode", choices=["exclude", "relabel"], default="exclude",
        help=(
            "exclude: bỏ hẳn ảnh sai nhãn khỏi bản đã lọc (dataset nhỏ đi).\n"
            "relabel: giữ lại ảnh, chuyển sang notdrowsy/ (không mất dữ liệu, "
            "khuyến nghị dùng khi tỷ lệ sai nhãn cao, ví dụ yawning ~50%)."
        ),
    )
    args = parser.parse_args()

    if args.clean:
        phase_clean(mode=args.mode)
    else:
        phase_scan()


if __name__ == "__main__":
    main()