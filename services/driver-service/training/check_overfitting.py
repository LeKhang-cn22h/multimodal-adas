"""Kiểm tra overfitting chuyên sâu cho model đã train.

Làm 2 việc mà log training thông thường KHÔNG cho thấy được:

1. SO SÁNH CÔNG BẰNG: tính lại accuracy/AUC trên tập TRAIN nhưng
   KHÔNG dùng augmentation (giống hệt cách tính val) — vì lúc training,
   train_acc bị "làm khó" bởi augmentation (xoay, zoom, đổi sáng) nên
   thấp hơn val_acc một cách giả tạo, không phản ánh đúng mức độ
   overfitting thật.

2. PHÂN TÍCH THEO SUBJECT (chỉ áp dụng cho task=eye, vì tên file MRL
   có subject_id): với val chỉ có 5-9 subject, kết quả tổng có thể bị
   lệch nếu 1-2 subject "dễ" chiếm phần lớn. Breakdown theo từng
   subject cho thấy model có ổn định qua các người khác nhau không,
   hay chỉ tốt nhờ vài subject dễ.

Cách đọc kết quả:
    - Nếu "Train (không augment) acc/auc" cao hơn HẲN "Val acc/auc"
      (chênh >5-10%) -> overfitting thật sự.
    - Nếu 2 con số gần nhau -> model generalize tốt, không overfit.
    - Nếu accuracy giữa các subject trong val dao động MẠNH (VD subject
      A đạt 99%, subject B chỉ 70%) -> model chưa tổng quát tốt, dù
      trung bình chung có thể vẫn "đẹp".

Chạy:
    python training/check_overfitting.py --task eye
    python training/check_overfitting.py --task mouth
"""

import argparse
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from torchvision import datasets

from configs.eye_config import EyeConfig
from configs.mouth_config import MouthConfig
from datasets.transforms import build_val_transform
from models.eye_cnn import build_eye_model
from models.mouth_cnn import build_mouth_model
from utils.checkpoint import load_checkpoint
from utils.metrics import compute_metrics

CONFIGS = {"eye": EyeConfig, "mouth": MouthConfig}
MODELS = {"eye": build_eye_model, "mouth": build_mouth_model}


def evaluate_loader(model, loader, device) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Trả về (y_true, y_pred, y_proba, filepaths) — giữ lại đường dẫn
    file để phân tích theo subject sau này."""
    model.eval()
    all_targets, all_probs, all_paths = [], [], []
    samples = loader.dataset.samples  # list of (path, class_idx), cùng thứ tự loader trả về khi shuffle=False

    with torch.no_grad():
        idx = 0
        for images, labels in loader:
            images = images.to(device)
            logits = model(images)
            probs = torch.sigmoid(logits).cpu().numpy().ravel()
            all_probs.extend(probs.tolist())
            all_targets.extend(labels.numpy().ravel().tolist())
            batch_size = images.size(0)
            all_paths.extend([samples[i][0] for i in range(idx, idx + batch_size)])
            idx += batch_size

    y_true = np.array(all_targets, dtype=int)
    y_proba = np.array(all_probs)
    y_pred = (y_proba >= 0.5).astype(int)
    return y_true, y_pred, y_proba, all_paths


def extract_subject_id(filepath: str) -> str | None:
    """Chỉ dùng được cho MRL (eye) — filename dạng
    s0001_00001_..._....png -> trả về 's0001'."""
    name = Path(filepath).stem
    parts = name.split("_")
    if parts and re.match(r"^s?\d+$", parts[0]):
        return parts[0]
    return None


def print_gap_analysis(train_metrics: dict, val_metrics: dict) -> None:
    print("\n" + "=" * 70)
    print("SO SÁNH TRAIN (không augment) vs VAL — cùng điều kiện đánh giá")
    print("=" * 70)
    header = f"{'Metric':<12}{'Train':>10}{'Val':>10}{'Chênh lệch':>14}"
    print(header)
    print("-" * 70)
    for key in ["accuracy", "precision", "recall", "f1", "auc"]:
        t, v = train_metrics[key], val_metrics[key]
        gap = t - v
        flag = "  <-- CHÊNH LỚN, nghi overfit" if gap > 0.05 else ""
        print(f"{key:<12}{t:>10.4f}{v:>10.4f}{gap:>+14.4f}{flag}")

    max_gap = max(train_metrics[k] - val_metrics[k] for k in ["accuracy", "auc"])
    print("-" * 70)
    if max_gap > 0.08:
        print("KẾT LUẬN: Chênh lệch train/val khá lớn -> CÓ dấu hiệu overfitting.")
        print("  Gợi ý: tăng augmentation, tăng dropout, giảm epoch, hoặc thêm data.")
    elif max_gap > 0.03:
        print("KẾT LUẬN: Chênh lệch nhẹ -> overfitting nhẹ, có thể chấp nhận được")
        print("  nhưng nên theo dõi thêm nếu train tiếp với nhiều epoch hơn.")
    else:
        print("KẾT LUẬN: Chênh lệch rất nhỏ -> model generalize tốt, KHÔNG có dấu hiệu overfit rõ ràng.")


def print_subject_breakdown(y_true, y_pred, y_proba, filepaths) -> None:
    subject_data = defaultdict(lambda: {"y_true": [], "y_pred": [], "y_proba": []})
    unmatched = 0
    for i, fp in enumerate(filepaths):
        sid = extract_subject_id(fp)
        if sid is None:
            unmatched += 1
            continue
        subject_data[sid]["y_true"].append(y_true[i])
        subject_data[sid]["y_pred"].append(y_pred[i])
        subject_data[sid]["y_proba"].append(y_proba[i])

    if not subject_data:
        print("\n(Không trích được subject_id từ tên file — bỏ qua phân tích theo subject.)")
        return

    print("\n" + "=" * 70)
    print(f"PHÂN TÍCH THEO SUBJECT trong tập VAL ({len(subject_data)} subject, {unmatched} ảnh không xác định được subject)")
    print("=" * 70)
    header = f"{'Subject':<10}{'#Ảnh':>8}{'Accuracy':>12}{'Recall':>10}{'AUC':>10}"
    print(header)
    print("-" * 70)

    accs = []
    for sid, d in sorted(subject_data.items()):
        yt = np.array(d["y_true"])
        yp = np.array(d["y_pred"])
        ypr = np.array(d["y_proba"])
        acc = (yt == yp).mean()
        recall = (yp[yt == 1] == 1).mean() if (yt == 1).sum() > 0 else float("nan")
        try:
            from sklearn.metrics import roc_auc_score
            auc = roc_auc_score(yt, ypr) if len(set(yt)) > 1 else float("nan")
        except Exception:
            auc = float("nan")
        accs.append(acc)
        flag = "  <-- thấp bất thường" if acc < 0.85 else ""
        print(f"{sid:<10}{len(yt):>8}{acc:>12.4f}{recall:>10.4f}{auc:>10.4f}{flag}")

    print("-" * 70)
    print(f"Accuracy trung bình các subject: {np.mean(accs):.4f}  |  Std: {np.std(accs):.4f}  |  Min: {np.min(accs):.4f}  |  Max: {np.max(accs):.4f}")
    if np.std(accs) > 0.08:
        print("-> Độ lệch chuẩn accuracy giữa các subject khá cao: model KHÔNG ổn định")
        print("   qua từng người, hiệu năng trung bình có thể đang bị 'kéo lên' bởi vài subject dễ.")
    else:
        print("-> Accuracy khá đồng đều giữa các subject: model tổng quát tốt qua nhiều người.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["eye", "mouth"], required=True)
    parser.add_argument("--checkpoint", type=str, default=None)
    args = parser.parse_args()

    cfg = CONFIGS[args.task]()
    checkpoint_path = args.checkpoint or cfg.model_path_pt

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MODELS[args.task](device)
    model = load_checkpoint(model, checkpoint_path, device)
    model.eval()

    # Cả train và val đều dùng val_transform (KHÔNG augmentation) để so sánh công bằng
    no_aug_transform = build_val_transform(cfg.img_size)

    train_ds = datasets.ImageFolder(cfg.data_dir / "train", transform=no_aug_transform)
    val_ds = datasets.ImageFolder(cfg.data_dir / "val", transform=no_aug_transform)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=2)

    print(f"Đang đánh giá lại TRAIN ({len(train_ds)} ảnh, không augmentation)...")
    yt_train, yp_train, ypr_train, paths_train = evaluate_loader(model, train_loader, device)
    train_metrics = compute_metrics(yt_train, yp_train, ypr_train)

    print(f"Đang đánh giá VAL ({len(val_ds)} ảnh)...")
    yt_val, yp_val, ypr_val, paths_val = evaluate_loader(model, val_loader, device)
    val_metrics = compute_metrics(yt_val, yp_val, ypr_val)

    print_gap_analysis(train_metrics, val_metrics)

    if args.task == "eye":
        print_subject_breakdown(yt_val, yp_val, ypr_val, paths_val)
    else:
        print("\n(Bỏ qua phân tích theo subject — Yawn Dataset không có subject_id trong tên file.)")


if __name__ == "__main__":
    main()