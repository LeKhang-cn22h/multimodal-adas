"""Vẽ biểu đồ đánh giá — training history, confusion matrix, ROC
curve. Dùng chung cho train_eye.py, train_mouth.py, evaluate.py."""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import roc_auc_score, roc_curve

matplotlib.use("Agg")


def plot_training_history(history1: dict, history2: dict, task_name: str, output_dir: Path) -> None:
    """Nối history 2 giai đoạn (freeze + fine-tune) thành 1 biểu đồ
    liên tục, có đường kẻ đứt đánh dấu lúc bắt đầu fine-tune."""
    combined = {k: history1[k] + history2.get(k, []) for k in history1}
    split_epoch = len(history1.get("loss", []))

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    metric_pairs = [
        ("loss", "val_loss", "Loss"), ("accuracy", "val_accuracy", "Accuracy"),
        ("auc", "val_auc", "AUC"), ("recall", "val_recall", "Recall"),
    ]
    for ax, (train_key, val_key, title) in zip(axes.flat, metric_pairs):
        if train_key not in combined:
            continue
        epochs = range(1, len(combined[train_key]) + 1)
        ax.plot(epochs, combined[train_key], label=f"Train {title}", color="steelblue")
        ax.plot(epochs, combined[val_key], label=f"Val {title}", color="darkorange")
        ax.axvline(split_epoch, color="gray", linestyle="--", linewidth=1, label="Bắt đầu fine-tune")
        ax.set_title(title)
        ax.set_xlabel("Epoch")
        ax.legend()
    fig.suptitle(f"Training History — {task_name}")
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_history.png", dpi=150)
    plt.close(fig)


def plot_confusion_matrix(y_true, y_pred, class_names: list[str], task_name: str, output_dir: Path) -> None:
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax, xticklabels=class_names, yticklabels=class_names)
    ax.set_title(f"Confusion Matrix — {task_name}")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_confusion_matrix.png", dpi=150)
    plt.close(fig)


def plot_roc_curve(y_true, y_proba, task_name: str, output_dir: Path) -> float:
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    auc_score = roc_auc_score(y_true, y_proba)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, color="crimson", label=f"AUC = {auc_score:.4f}")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(f"ROC Curve — {task_name}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_roc_curve.png", dpi=150)
    plt.close(fig)
    return auc_score