"""Step 3 — Engineer 40 features from intermediate CSV.

Reads dataset_intermediate.csv, groups by (subject_id, scenario),
creates a fresh WindowedFeatureEngineer per group (same module as
runtime), computes all 40 features + label_smoothed, and applies
strict cut-off (drop frames with perclos_depth < 900).

Output: training/output/dataset_features.csv
    40 feature columns + label_binary + label_smoothed
"""

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.services.feature_engineering import WindowedFeatureEngineer
from app.utils.logger import get_logger

logger = get_logger()

INPUT_CSV = Path("training/output/dataset_intermediate.csv")
OUTPUT_CSV = Path("training/output/dataset_features.csv")

LABEL_SMOOTH = 30   # centered window, 1 second @ 30 fps
N_CUTOFF = 899      # N_PERCLOS - 1, strict cut-off per group

ROOT_COLUMNS = [
    "ear_left", "ear_right", "ear_avg",
    "mar", "yaw", "pitch", "roll",
]


def smooth_labels(group: pd.DataFrame) -> pd.Series:
    """Centered-window majority-vote label smoothing.

    Only applied when the group has both 0 and 1 labels.
    Returns a Series with the same index as group.
    """
    labels = group["label_binary"].values
    n = len(labels)

    if len(np.unique(labels)) < 2:
        # Single class — no boundary to smooth
        return group["label_binary"]

    smoothed = np.zeros_like(labels, dtype=int)
    half = LABEL_SMOOTH // 2

    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half)
        window = labels[start:end]
        counter = Counter(window)
        smoothed[i] = counter.most_common(1)[0][0]

    return pd.Series(smoothed, index=group.index, dtype=int)


def main() -> None:
    settings = get_settings()

    logger.info("Loading %s...", INPUT_CSV)
    df = pd.read_csv(INPUT_CSV)
    logger.info("Loaded %d rows", len(df))

    df.sort_values(["subject_id", "scenario", "frame_number"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    all_rows: list[dict] = []
    total_dropped = 0
    n_groups = 0

    grouped = df.groupby(["subject_id", "scenario"], sort=False)

    for (subj, sc), group in tqdm(grouped, desc="Engineering features"):
        n_groups += 1
        group = group.sort_values("frame_number").reset_index(drop=True)

        engine = WindowedFeatureEngineer(
            n_stat=settings.N_STAT,
            n_perclos=settings.N_PERCLOS,
            n_vel=settings.N_VEL,
            ear_threshold=settings.EAR_THRESHOLD,
            fps=settings.FPS_ASSUMPTION,
        )

        # Compute raw features (no cut-off yet — expanding window)
        raw_rows: list[dict] = []
        for _, row in group.iterrows():
            roots = {col: float(row[col]) for col in ROOT_COLUMNS}
            fv_dict = engine.update(roots)
            fv_dict["subject_id"] = subj
            fv_dict["scenario"] = sc
            fv_dict["label_binary"] = int(row["label_binary"])
            fv_dict["__depth"] = engine.perclos_depth
            raw_rows.append(fv_dict)

        # Apply strict cut-off
        kept = [r for r in raw_rows if r["__depth"] >= N_CUTOFF]
        dropped_this_group = len(raw_rows) - len(kept)
        total_dropped += dropped_this_group

        for r in kept:
            del r["__depth"]
        all_rows.extend(kept)

    pct_dropped = (
        100.0 * total_dropped / (total_dropped + len(all_rows))
        if (total_dropped + len(all_rows)) > 0
        else 0.0
    )
    logger.info(
        "Groups: %d, dropped: %d (%.2f%%)",
        n_groups, total_dropped, pct_dropped,
    )

    result_df = pd.DataFrame(all_rows)

    # ── Label smoothing (per group, centered window) ────────────────
    logger.info("Smoothing labels...")
    smoothed_labels: list[int] = []
    for (_subj, _sc), group in tqdm(
        result_df.groupby(["subject_id", "scenario"], sort=False),
        desc="Smoothing",
    ):
        s = smooth_labels(group)
        smoothed_labels.extend(s.tolist())

    result_df = result_df.sort_index()
    result_df["label_smoothed"] = smoothed_labels

    # Move label columns to end
    cols = [
        c for c in result_df.columns
        if c not in ("label_binary", "label_smoothed")
    ]
    cols += ["label_binary", "label_smoothed"]
    result_df = result_df[cols]

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUTPUT_CSV, index=False)
    logger.info("Output: %s (%d rows)", OUTPUT_CSV, len(result_df))

    # Log smoothing stats
    changed = (
        result_df["label_binary"] != result_df["label_smoothed"]
    ).sum()
    logger.info(
        "Labels changed by smoothing: %d (%.2f%%)",
        changed, 100.0 * changed / len(result_df),
    )


if __name__ == "__main__":
    main()
