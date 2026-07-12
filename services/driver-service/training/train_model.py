"""Step 6 — Train RandomForest vs XGBoost with LOSO-CV, save best model.

Performs 4-fold LOSO-CV (one subject per fold, 4 subjects total),
compares mean ROC-AUC between RF and XGBoost, trains the winning
model on all 4 subjects, and saves it as model.pkl.

Also generates:
    - loso_comparison.png          (bar chart: 4 metrics mean±std)
    - loso_roc_comparison.png      (aggregate ROC curves)
    - confusion_matrix_{rf,xgb}.png
    - feature_importance_{winner}.png  (top-20)
    - training_report.txt
"""

import sys
from pathlib import Path

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from tqdm import tqdm
from xgboost import XGBClassifier

matplotlib.use("Agg")  # non-interactive backend

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logger import get_logger

logger = get_logger()

INPUT_CSV = Path("training/output/dataset_features.csv")
OUTPUT_DIR = Path("training/output")
MODEL_PATH = OUTPUT_DIR / "model.pkl"

# ── 40 feature columns (order must match FeatureVector.to_array()) ──
FEATURE_COLS = [
    # Root (7)
    "ear_left", "ear_right", "ear_avg",
    "mar", "yaw", "pitch", "roll",
    # Statistics (28) — N=300 backward
    "ear_left_mean", "ear_left_std", "ear_left_min", "ear_left_max",
    "ear_right_mean", "ear_right_std", "ear_right_min", "ear_right_max",
    "ear_avg_mean", "ear_avg_std", "ear_avg_min", "ear_avg_max",
    "mar_mean", "mar_std", "mar_min", "mar_max",
    "yaw_mean", "yaw_std", "yaw_min", "yaw_max",
    "pitch_mean", "pitch_std", "pitch_min", "pitch_max",
    "roll_mean", "roll_std", "roll_min", "roll_max",
    # Temporal (5)
    "perclos", "blink_rate",
    "yaw_velocity", "pitch_velocity", "roll_velocity",
]

# ── Model configs ──────────────────────────────────────────────────
RF_PARAMS = {
    "n_estimators": 100,
    "max_depth": 10,
    "random_state": 42,
    "class_weight": "balanced",
    "n_jobs": -1,
}

XGB_PARAMS = {
    "n_estimators": 100,
    "max_depth": 6,
    "learning_rate": 0.1,
    "random_state": 42,
    "eval_metric": "logloss",
}


# =========================================================================
# Helpers
# =========================================================================


def make_model(model_type: str):
    """Factory: create a fresh model instance."""
    if model_type == "RF":
        return RandomForestClassifier(**RF_PARAMS)
    return XGBClassifier(**XGB_PARAMS)


def loso_cv(df: pd.DataFrame, model_type: str) -> list[dict]:
    """Leave-One-Subject-Out cross-validation.

    Returns list of per-fold result dicts with metrics + raw predictions
    (for aggregate charts).
    """
    subjects = sorted(df["subject_id"].unique())
    results: list[dict] = []

    for test_subject in tqdm(subjects, desc=f"{model_type} LOSO-CV"):
        train_mask = df["subject_id"] != test_subject
        X_train = df.loc[train_mask, FEATURE_COLS].values
        y_train = df.loc[train_mask, "label_smoothed"].values
        X_test = df.loc[~train_mask, FEATURE_COLS].values
        y_test = df.loc[~train_mask, "label_smoothed"].values

        model = make_model(model_type)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)
        drowsy_idx = list(model.classes_).index(1)

        results.append({
            "test_subject": test_subject,
            "n_train": len(X_train),
            "n_test": len(X_test),
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, y_proba[:, drowsy_idx]),
            "y_test": y_test,
            "y_pred": y_pred,
            "y_proba": y_proba[:, drowsy_idx],
        })

    return results


def print_per_fold_table(results: list[dict], model_type: str) -> dict:
    """Print per-fold metrics table.  Returns mean dict."""
    print(f"\n{'='*70}")
    print(f"  {model_type} — LOSO-CV Results")
    print(f"{'='*70}")
    header = (
        f"{'Fold':>4}  {'Subject':>7}  {'#Train':>7}  {'#Test':>6}  "
        f"{'Acc':>7}  {'F1':>7}  {'Recall':>5}  {'AUC':>7}"
    )
    print(header)
    print("-" * 70)

    for i, r in enumerate(results, 1):
        print(
            f"{i:>4}  {r['test_subject']:>7}  {r['n_train']:>7}  "
            f"{r['n_test']:>6}  {r['accuracy']:>7.4f}  "
            f"{r['f1']:>7.4f}  {r['recall']:>5.4f}  "
            f"{r['roc_auc']:>7.4f}"
        )

    metric_keys = ["accuracy", "f1", "recall", "roc_auc"]
    means = {k: float(np.mean([r[k] for r in results])) for k in metric_keys}
    stds = {k: float(np.std([r[k] for r in results])) for k in metric_keys}
    print("-" * 70)
    print(
        f"{'Mean ± Std':>13}  {'':>7}  {'':>7}  "
        f"{means['accuracy']:>7.4f}  {means['f1']:>7.4f}  "
        f"{means['recall']:>5.4f}  {means['roc_auc']:>7.4f}"
    )
    print(
        f"{'':>13}  {'':>7}  {'':>7}  "
        f"±{stds['accuracy']:.4f}  ±{stds['f1']:.4f}  "
        f"±{stds['recall']:.4f}  ±{stds['roc_auc']:.4f}"
    )
    return means


# =========================================================================
# Charts
# =========================================================================


def plot_comparison(
    rf_results: list[dict],
    xgb_results: list[dict],
) -> None:
    """Generate comparison bar chart + ROC curves + confusion matrices."""
    sns.set_style("whitegrid")

    # ── Bar chart ─────────────────────────────────────────────────
    metrics = ["accuracy", "f1", "recall", "roc_auc"]
    rf_means = [np.mean([r[m] for r in rf_results]) for m in metrics]
    rf_stds = [np.std([r[m] for r in rf_results]) for m in metrics]
    xgb_means = [np.mean([r[m] for r in xgb_results]) for m in metrics]
    xgb_stds = [np.std([r[m] for r in xgb_results]) for m in metrics]

    x = np.arange(len(metrics))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(
        x - width / 2, rf_means, width, yerr=rf_stds,
        label="Random Forest", capsize=5,
    )
    ax.bar(
        x + width / 2, xgb_means, width, yerr=xgb_stds,
        label="XGBoost", capsize=5,
    )
    ax.set_ylabel("Score")
    ax.set_title("LOSO-CV: Random Forest vs XGBoost (mean ± std)")
    ax.set_xticks(x)
    ax.set_xticklabels([m.upper() for m in metrics])
    ax.legend()
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "loso_comparison.png", dpi=150)
    plt.close(fig)

    # ── ROC curves (aggregate) ────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 6))
    for label, results, color in [
        ("Random Forest", rf_results, "blue"),
        ("XGBoost", xgb_results, "red"),
    ]:
        all_y = np.concatenate([r["y_test"] for r in results])
        all_proba = np.concatenate([r["y_proba"] for r in results])
        fpr, tpr, _ = roc_curve(all_y, all_proba)
        auc = roc_auc_score(all_y, all_proba)
        ax.plot(fpr, tpr, label=f"{label} (AUC={auc:.4f})", color=color)
    ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("Aggregate ROC Curves (LOSO-CV)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "loso_roc_comparison.png", dpi=150)
    plt.close(fig)

    # ── Confusion matrices ────────────────────────────────────────
    for label, results in [("rf", rf_results), ("xgb", xgb_results)]:
        all_y = np.concatenate([r["y_test"] for r in results])
        all_pred = np.concatenate([r["y_pred"] for r in results])
        cm = confusion_matrix(all_y, all_pred)
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="Blues", ax=ax,
            xticklabels=["Not Drowsy", "Drowsy"],
            yticklabels=["Not Drowsy", "Drowsy"],
        )
        ax.set_title(f"Confusion Matrix — {label.upper()} (aggregate)")
        ax.set_ylabel("Actual")
        ax.set_xlabel("Predicted")
        fig.tight_layout()
        fig.savefig(
            OUTPUT_DIR / f"confusion_matrix_{label}.png", dpi=150,
        )
        plt.close(fig)


def write_report(
    rf_results: list[dict],
    xgb_results: list[dict],
    winner: str,
    model,
    reason: str,
) -> None:
    """Write training_report.txt."""
    rf_mean_auc = np.mean([r["roc_auc"] for r in rf_results])
    xgb_mean_auc = np.mean([r["roc_auc"] for r in xgb_results])

    with open(OUTPUT_DIR / "training_report.txt", "w") as f:
        f.write("NTHU-DDD Drowsiness Detection — Training Report\n")
        f.write("=" * 60 + "\n\n")
        f.write("Subjects: 001, 002, 005, 006 (4 total)\n")
        f.write(f"Features: {len(FEATURE_COLS)}\n")
        f.write("CV method: LOSO-CV (4-fold)\n\n")

        f.write(
            f"Random Forest — mean ROC-AUC: {rf_mean_auc:.4f} ± "
            f"{np.std([r['roc_auc'] for r in rf_results]):.4f}\n"
        )
        f.write(
            f"XGBoost       — mean ROC-AUC: {xgb_mean_auc:.4f} ± "
            f"{np.std([r['roc_auc'] for r in xgb_results]):.4f}\n\n"
        )
        f.write(f"Winner: {winner}\n")
        f.write(f"Reason: {reason}\n\n")

        f.write(f"Production model: {type(model).__name__}\n")
        f.write(f"Saved to: {MODEL_PATH}\n")
        size_kb = MODEL_PATH.stat().st_size / 1024
        f.write(f"Model size: {size_kb:.1f} KB\n\n")

        f.write(
            "Limitations: 4 subjects only. Generalization to "
            "unseen subjects may be limited.\n"
        )

    logger.info("Report: %s", OUTPUT_DIR / "training_report.txt")


# =========================================================================
# Main
# =========================================================================


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Loading %s...", INPUT_CSV)
    df = pd.read_csv(INPUT_CSV)
    logger.info("Loaded %d rows, %d features", len(df), len(FEATURE_COLS))

    subjects = sorted(df["subject_id"].unique())
    logger.info("Subjects: %s", subjects)

    # ── LOSO-CV: Random Forest ────────────────────────────────────
    logger.info("Running LOSO-CV for Random Forest...")
    rf_results = loso_cv(df, "RF")
    print_per_fold_table(rf_results, "Random Forest")

    # ── LOSO-CV: XGBoost ──────────────────────────────────────────
    logger.info("Running LOSO-CV for XGBoost...")
    xgb_results = loso_cv(df, "XGB")
    print_per_fold_table(xgb_results, "XGBoost")

    # ── Select winner ─────────────────────────────────────────────
    rf_mean_auc = float(np.mean([r["roc_auc"] for r in rf_results]))
    xgb_mean_auc = float(np.mean([r["roc_auc"] for r in xgb_results]))
    delta = abs(rf_mean_auc - xgb_mean_auc)

    if delta < 0.01:
        # Tie-break by F1
        rf_mean_f1 = float(np.mean([r["f1"] for r in rf_results]))
        xgb_mean_f1 = float(np.mean([r["f1"] for r in xgb_results]))
        if rf_mean_f1 >= xgb_mean_f1:
            winner = "RandomForest"
            reason = (
                f"Δ ROC-AUC < 0.01, selected by mean F1 "
                f"(RF={rf_mean_f1:.4f}, XGB={xgb_mean_f1:.4f})"
            )
        else:
            winner = "XGBoost"
            reason = (
                f"Δ ROC-AUC < 0.01, selected by mean F1 "
                f"(XGB={xgb_mean_f1:.4f}, RF={rf_mean_f1:.4f})"
            )
    elif rf_mean_auc >= xgb_mean_auc:
        winner = "RandomForest"
        reason = f"Higher mean ROC-AUC (RF={rf_mean_auc:.4f} > XGB={xgb_mean_auc:.4f})"
    else:
        winner = "XGBoost"
        reason = f"Higher mean ROC-AUC (XGB={xgb_mean_auc:.4f} > RF={rf_mean_auc:.4f})"

    logger.info("Winner: %s — %s", winner, reason)

    # ── Train production model on all 4 subjects ──────────────────
    logger.info(
        "Training production model (%s) on all subjects...", winner,
    )
    X_all = df[FEATURE_COLS].values
    y_all = df["label_smoothed"].values

    model_type = "RF" if winner == "RandomForest" else "XGB"
    prod_model = make_model(model_type)
    prod_model.fit(X_all, y_all)

    joblib.dump(prod_model, MODEL_PATH)
    size_kb = MODEL_PATH.stat().st_size / 1024
    logger.info("Model saved: %s (%.1f KB)", MODEL_PATH, size_kb)

    # ── Charts ────────────────────────────────────────────────────
    logger.info("Generating charts...")
    plot_comparison(rf_results, xgb_results)

    # Feature importance (production model)
    if hasattr(prod_model, "feature_importances_"):
        importances = prod_model.feature_importances_
        indices = np.argsort(importances)[-20:]
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.barh(range(20), importances[indices])
        ax.set_yticks(range(20))
        ax.set_yticklabels([FEATURE_COLS[i] for i in indices])
        ax.set_xlabel("Importance")
        ax.set_title(f"Top-20 Feature Importance — {winner}")
        fig.tight_layout()
        fig.savefig(
            OUTPUT_DIR / f"feature_importance_{winner.lower()}.png",
            dpi=150,
        )
        plt.close(fig)

    # ── Report ────────────────────────────────────────────────────
    write_report(rf_results, xgb_results, winner, prod_model, reason)

    logger.info("Done! Model: %s", MODEL_PATH)


if __name__ == "__main__":
    main()
