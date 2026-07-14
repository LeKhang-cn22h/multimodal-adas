"""Entry point train task eye. Chạy:
    python training/train_eye.py
    python training/train_eye.py --epochs 20 --batch-size 64
"""

import argparse

import torch

from configs.eye_config import EyeConfig
from datasets.eye_dataset import get_eye_dataloaders
from models.common import compute_pos_weight
from models.eye_cnn import build_eye_model
from trainers.trainer import Trainer
from utils.checkpoint import save_checkpoint
from utils.metrics import get_classification_report
from utils.plots import plot_all
from utils.seed import set_seed


def write_report(
    cfg: EyeConfig, n_train: int, n_val: int, y_true, y_pred, y_proba, metrics: dict,
    roc_auc: float, pr_auc: float,
) -> None:
    report_txt = get_classification_report(y_true, y_pred, cfg.classes)
    pt_size = cfg.model_path_pt.stat().st_size / 1024

    lines = [
        f"CNN Training Report (PyTorch, modular) — task: {cfg.task_name}", "=" * 60,
        f"Train samples: {n_train}", f"Val samples: {n_val}",
        f"Classes: {cfg.classes}", f"Input size: {cfg.img_size}x{cfg.img_size}", "",
        "VAL METRICS (threshold=0.5)", "-" * 60,
        f"Accuracy:  {metrics['accuracy']:.4f}", f"Precision: {metrics['precision']:.4f}",
        f"Recall:    {metrics['recall']:.4f}", f"F1:        {metrics['f1']:.4f}",
        f"ROC-AUC:   {roc_auc:.4f}", f"PR-AUC:    {pr_auc:.4f}", "",
        "Classification report (per class):", report_txt, "",
        f"Model (.pt): {cfg.model_path_pt}  ({pt_size:.1f} KB)",
        "", "Charts:",
        f"  - cnn_{cfg.task_name}_history.png",
        f"  - cnn_{cfg.task_name}_loss.png",
        f"  - cnn_{cfg.task_name}_accuracy.png",
        f"  - cnn_{cfg.task_name}_auc.png",
        f"  - cnn_{cfg.task_name}_lr_curve.png",
        f"  - cnn_{cfg.task_name}_confusion_matrix.png",
        f"  - cnn_{cfg.task_name}_confusion_matrix_norm.png",
        f"  - cnn_{cfg.task_name}_roc_curve.png",
        f"  - cnn_{cfg.task_name}_pr_curve.png",
        f"  - cnn_{cfg.task_name}_prediction_samples.png",
    ]
    cfg.report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Báo cáo: {cfg.report_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs_head")
    parser.add_argument("--epochs-finetune", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=None, help="Giảm xuống nếu gặp lỗi shared memory trên Windows (thử 2, hoặc 0)")
    parser.add_argument("--no-amp", action="store_true")
    args = parser.parse_args()

    cfg = EyeConfig()
    if args.epochs is not None:
        cfg.epochs_head = args.epochs
    if args.epochs_finetune is not None:
        cfg.epochs_finetune = args.epochs_finetune
    if args.batch_size is not None:
        cfg.batch_size = args.batch_size
    if args.num_workers is not None:
        cfg.num_workers = args.num_workers

    set_seed(cfg.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))

    train_loader, val_loader, train_ds, val_ds = get_eye_dataloaders(cfg)
    print(f"Train: {len(train_ds)} ảnh | Val: {len(val_ds)} ảnh | classes: {train_ds.class_to_idx}")

    model = build_eye_model(device)
    pos_weight = compute_pos_weight(train_ds).to(device)
    print(f"pos_weight: {pos_weight.item():.3f}")

    trainer = Trainer(model, device, pos_weight, patience=cfg.patience, use_amp=not args.no_amp)
    history1, history2 = trainer.fit(
        train_loader, val_loader,
        epochs_head=cfg.epochs_head, epochs_finetune=cfg.epochs_finetune,
        lr_head=cfg.lr_head, lr_finetune=cfg.lr_finetune,
        unfreeze_last_n=cfg.unfreeze_last_n,
    )

    save_checkpoint(model, cfg.model_path_pt)

    metrics, y_true, y_pred, y_proba = trainer.evaluate(val_loader)
    print(f"\nKết quả VAL cuối cùng: {metrics}")

    # Lấy ảnh mẫu (tối đa 16) từ tập val để vẽ lưới dự đoán minh hoạ
    sample_images, sample_y_true, sample_y_pred, sample_y_proba = trainer.sample_predictions(val_loader, n=16)

    auc_scores = plot_all(
        history1, history2, y_true, y_pred, y_proba, cfg.classes, cfg.task_name, cfg.output_dir,
        sample_images=sample_images, sample_y_true=sample_y_true,
        sample_y_pred=sample_y_pred, sample_y_proba=sample_y_proba,
    )

    write_report(
        cfg, len(train_ds), len(val_ds), y_true, y_pred, y_proba, metrics,
        roc_auc=auc_scores["roc_auc"], pr_auc=auc_scores["pr_auc"],
    )

    print(f"\nHoàn tất task '{cfg.task_name}'. Chạy training/export_onnx.py --task eye để xuất ONNX.")


if __name__ == "__main__":
    main()