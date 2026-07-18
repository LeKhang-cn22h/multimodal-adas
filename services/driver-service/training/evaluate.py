"""Đánh giá lại 1 checkpoint đã train, không cần train lại từ đầu.
Hữu ích khi bạn đổi ngưỡng, muốn vẽ lại biểu đồ, hoặc so sánh nhiều
checkpoint khác nhau.

Chạy:
    python training/evaluate.py --task eye
    python training/evaluate.py --task mouth --checkpoint path/to/other_model.pt
"""

import argparse

import torch

from configs.eye_config import EyeConfig
from configs.mouth_config import MouthConfig
from datasets.eye_dataset import get_eye_dataloaders
from datasets.mouth_dataset import get_mouth_dataloaders
from models.eye_cnn import build_eye_model
from models.mouth_cnn import build_mouth_model
from utils.checkpoint import load_checkpoint
from utils.metrics import get_classification_report
from utils.plots import plot_confusion_matrix, plot_roc_curve

CONFIGS = {"eye": EyeConfig, "mouth": MouthConfig}
DATALOADERS = {"eye": get_eye_dataloaders, "mouth": get_mouth_dataloaders}
MODELS = {"eye": build_eye_model, "mouth": build_mouth_model}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["eye", "mouth"], required=True)
    parser.add_argument("--checkpoint", type=str, default=None, help="Đường dẫn .pt tuỳ chọn (mặc định dùng model_path_pt trong config)")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    cfg = CONFIGS[args.task]()
    checkpoint_path = args.checkpoint or cfg.model_path_pt

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    _, val_loader, _, val_ds = DATALOADERS[args.task](cfg)
    print(f"Val: {len(val_ds)} ảnh | classes: {val_ds.class_to_idx}")

    model = MODELS[args.task](device)
    model = load_checkpoint(model, checkpoint_path, device)
    model.eval()

    import numpy as np
    all_targets, all_probs = [], []
    with torch.no_grad():
        for images, labels in val_loader:
            images = images.to(device)
            logits = model(images)
            probs = torch.sigmoid(logits).cpu().numpy().ravel()
            all_probs.extend(probs.tolist())
            all_targets.extend(labels.numpy().ravel().tolist())

    y_true = np.array(all_targets, dtype=int)
    y_proba = np.array(all_probs)
    y_pred = (y_proba >= args.threshold).astype(int)

    print(f"\nClassification report (threshold={args.threshold}):")
    print(get_classification_report(y_true, y_pred, cfg.classes))

    plot_confusion_matrix(y_true, y_pred, cfg.classes, f"{cfg.task_name}_reeval", cfg.output_dir)
    auc_score = plot_roc_curve(y_true, y_proba, f"{cfg.task_name}_reeval", cfg.output_dir)
    print(f"AUC: {auc_score:.4f}")
    print(f"\nBiểu đồ mới: cnn_{cfg.task_name}_reeval_confusion_matrix.png, cnn_{cfg.task_name}_reeval_roc_curve.png")


if __name__ == "__main__":
    main()