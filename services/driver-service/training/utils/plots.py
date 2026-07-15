"""Vẽ biểu đồ đánh giá — training history, loss/accuracy/auc riêng lẻ,
LR curve, confusion matrix (raw + normalized), ROC curve, PR curve,
và lưới ảnh dự đoán mẫu. Dùng chung cho train_eye.py, train_mouth.py,
evaluate.py."""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

matplotlib.use("Agg")

# Chuẩn hoá ImageNet mặc định (đa số backbone transfer-learning dùng chuẩn này).
# Nếu dataset của bạn dùng mean/std khác, truyền lại qua tham số mean/std của
# plot_prediction_samples.
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406])
IMAGENET_STD = np.array([0.229, 0.224, 0.225])


def _combine_history(history1: dict, history2: dict) -> tuple[dict, int]:
    combined = {k: history1[k] + history2.get(k, []) for k in history1}
    split_epoch = len(history1.get("loss", []))
    return combined, split_epoch


def plot_training_history(history1: dict, history2: dict, task_name: str, output_dir: Path) -> None:
    """Nối history 2 giai đoạn (freeze + fine-tune) thành 1 biểu đồ
    liên tục, có đường kẻ đứt đánh dấu lúc bắt đầu fine-tune."""
    combined, split_epoch = _combine_history(history1, history2)

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


def _plot_single_metric(
    history1: dict, history2: dict, metric_key: str, title: str,
    task_name: str, output_dir: Path, filename_suffix: str,
    color_train: str = "steelblue", color_val: str = "darkorange",
) -> None:
    """Vẽ 1 biểu đồ riêng cho 1 metric (train vs val), dùng cho
    loss.png / accuracy.png / auc.png tách biệt khỏi history.png tổng."""
    combined, split_epoch = _combine_history(history1, history2)
    val_key = f"val_{metric_key}"
    if metric_key not in combined:
        print(f"  [plots] Bỏ qua '{metric_key}': không có trong history.")
        return

    epochs = range(1, len(combined[metric_key]) + 1)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(epochs, combined[metric_key], label=f"Train {title}", color=color_train, marker="o", markersize=3)
    if val_key in combined:
        ax.plot(epochs, combined[val_key], label=f"Val {title}", color=color_val, marker="o", markersize=3)
    if split_epoch:
        ax.axvline(split_epoch, color="gray", linestyle="--", linewidth=1, label="Bắt đầu fine-tune")
    ax.set_title(f"{title} — {task_name}")
    ax.set_xlabel("Epoch")
    ax.set_ylabel(title)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_{filename_suffix}.png", dpi=150)
    plt.close(fig)


def plot_loss_curve(history1: dict, history2: dict, task_name: str, output_dir: Path) -> None:
    _plot_single_metric(history1, history2, "loss", "Loss", task_name, output_dir, "loss")


def plot_accuracy_curve(history1: dict, history2: dict, task_name: str, output_dir: Path) -> None:
    _plot_single_metric(history1, history2, "accuracy", "Accuracy", task_name, output_dir, "accuracy")


def plot_auc_curve(history1: dict, history2: dict, task_name: str, output_dir: Path) -> None:
    _plot_single_metric(history1, history2, "auc", "AUC", task_name, output_dir, "auc")


def plot_lr_curve(history1: dict, history2: dict, task_name: str, output_dir: Path) -> None:
    """Vẽ learning rate theo epoch (bậc thang giữa 2 giai đoạn train
    head / fine-tune). Cần Trainer ghi lại history['lr'] mỗi epoch."""
    combined, split_epoch = _combine_history(history1, history2)
    if "lr" not in combined:
        print("  [plots] Bỏ qua LR curve: history không có key 'lr'.")
        return

    epochs = range(1, len(combined["lr"]) + 1)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.step(epochs, combined["lr"], where="post", color="seagreen", linewidth=2)
    if split_epoch:
        ax.axvline(split_epoch, color="gray", linestyle="--", linewidth=1, label="Bắt đầu fine-tune")
        ax.legend()
    ax.set_yscale("log")
    ax.set_title(f"Learning Rate — {task_name}")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Learning rate (log scale)")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_lr_curve.png", dpi=150)
    plt.close(fig)


def plot_confusion_matrix(y_true, y_pred, class_names: list[str], task_name: str, output_dir: Path) -> None:
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax, xticklabels=class_names, yticklabels=class_names)
    ax.set_title(f"Confusion Matrix — {task_name}")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_confusion_matrix.png", dpi=150)
    plt.close(fig)


def plot_confusion_matrix_normalized(y_true, y_pred, class_names: list[str], task_name: str, output_dir: Path) -> None:
    """Confusion matrix chuẩn hoá theo hàng (tỉ lệ % trên mỗi lớp thật),
    hữu ích khi 2 lớp mất cân bằng số lượng mẫu."""
    cm_norm = confusion_matrix(y_true, y_pred, normalize="true")
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        cm_norm, annot=True, fmt=".2%", cmap="Blues", ax=ax,
        xticklabels=class_names, yticklabels=class_names, vmin=0, vmax=1,
    )
    ax.set_title(f"Confusion Matrix (normalized) — {task_name}")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_confusion_matrix_norm.png", dpi=150)
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


def plot_pr_curve(y_true, y_proba, task_name: str, output_dir: Path) -> float:
    """Precision-Recall curve — thường thông tin hơn ROC khi lớp
    positive (mắt nhắm / miệng ngáp) là thiểu số."""
    precision, recall, _ = precision_recall_curve(y_true, y_proba)
    ap_score = average_precision_score(y_true, y_proba)
    baseline = float(np.mean(y_true))

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(recall, precision, color="purple", label=f"AP = {ap_score:.4f}")
    ax.axhline(baseline, color="k", linestyle="--", alpha=0.3, label=f"Baseline = {baseline:.3f}")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(f"Precision-Recall Curve — {task_name}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_pr_curve.png", dpi=150)
    plt.close(fig)
    return ap_score


def plot_prediction_samples(
    images: "np.ndarray | object",
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    class_names: list[str],
    task_name: str,
    output_dir: Path,
    n: int = 16,
    mean: np.ndarray = IMAGENET_MEAN,
    std: np.ndarray = IMAGENET_STD,
) -> None:
    """Vẽ lưới ảnh mẫu kèm nhãn thật/dự đoán, viền xanh nếu đúng,
    viền đỏ nếu sai. `images` là tensor/array shape (N, C, H, W) đã
    qua transform (chuẩn hoá) — sẽ được denormalize lại để hiển thị.
    """
    images_np = images.detach().cpu().numpy() if hasattr(images, "detach") else np.asarray(images)
    n = min(n, images_np.shape[0])
    n_cols = 4
    n_rows = int(np.ceil(n / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3 * n_cols, 3.2 * n_rows))
    axes = np.atleast_1d(axes).ravel()

    for i in range(n_rows * n_cols):
        ax = axes[i]
        ax.axis("off")
        if i >= n:
            continue

        img = np.transpose(images_np[i], (1, 2, 0))  # CHW -> HWC
        if img.shape[-1] == 3:
            img = img * std + mean
        img = np.clip(img, 0, 1)
        if img.shape[-1] == 1:
            ax.imshow(img.squeeze(-1), cmap="gray")
        else:
            ax.imshow(img)

        true_label = class_names[int(y_true[i])]
        pred_label = class_names[int(y_pred[i])]
        correct = int(y_true[i]) == int(y_pred[i])
        color = "green" if correct else "red"
        ax.set_title(f"Thật: {true_label}\nDự đoán: {pred_label} ({y_proba[i]:.2f})", color=color, fontsize=9)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor(color)
            spine.set_linewidth(2)

    fig.suptitle(f"Mẫu dự đoán trên tập Val — {task_name}")
    fig.tight_layout()
    fig.savefig(output_dir / f"cnn_{task_name}_prediction_samples.png", dpi=150)
    plt.close(fig)


def plot_all(
    history1: dict,
    history2: dict,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    class_names: list[str],
    task_name: str,
    output_dir: Path,
    sample_images=None,
    sample_y_true=None,
    sample_y_pred=None,
    sample_y_proba=None,
) -> dict:
    """Tiện ích gọi 1 lần vẽ hết mọi biểu đồ báo cáo cần.
    Trả về dict {"roc_auc": ..., "pr_auc": ...}.
    Nếu có sample_images (ảnh mẫu lấy từ trainer.sample_predictions),
    sẽ vẽ luôn cnn_<task>_prediction_samples.png.
    """
    output_dir = Path(output_dir)
    plot_training_history(history1, history2, task_name, output_dir)
    plot_loss_curve(history1, history2, task_name, output_dir)
    plot_accuracy_curve(history1, history2, task_name, output_dir)
    plot_auc_curve(history1, history2, task_name, output_dir)
    plot_lr_curve(history1, history2, task_name, output_dir)

    plot_confusion_matrix(y_true, y_pred, class_names, task_name, output_dir)
    plot_confusion_matrix_normalized(y_true, y_pred, class_names, task_name, output_dir)

    roc_auc = plot_roc_curve(y_true, y_proba, task_name, output_dir)
    pr_auc = plot_pr_curve(y_true, y_proba, task_name, output_dir)

    if sample_images is not None:
        plot_prediction_samples(
            sample_images, sample_y_true, sample_y_pred, sample_y_proba,
            class_names, task_name, output_dir,
        )

    return {"roc_auc": roc_auc, "pr_auc": pr_auc}