"""Kiến trúc CNN dùng chung cho cả eye và mouth — MobileNetV2 transfer
learning. eye_cnn.py và mouth_cnn.py chỉ gọi lại các hàm ở đây."""

import numpy as np
import torch
import torch.nn as nn
from torchvision import datasets, models


def build_mobilenet_classifier(device: torch.device) -> nn.Module:
    """MobileNetV2 pretrain ImageNet, backbone đóng băng, thay
    classifier head bằng head nhị phân (output: raw logit, dùng với
    BCEWithLogitsLoss)."""
    backbone = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    for param in backbone.features.parameters():
        param.requires_grad = False

    in_features = backbone.classifier[1].in_features  # 1280
    backbone.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 64),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Linear(64, 1),
    )
    return backbone.to(device)


def unfreeze_top_layers(model: nn.Module, n_layers: int = 30) -> None:
    """Mở khoá n_layers module cuối của model.features để fine-tune."""
    feature_modules = list(model.features.children())
    for layer in feature_modules[-n_layers:]:
        for p in layer.parameters():
            p.requires_grad = True


def compute_pos_weight(train_ds: datasets.ImageFolder) -> torch.Tensor:
    """pos_weight cho BCEWithLogitsLoss, cân bằng lớp 0/1 (ImageFolder
    gán index theo thứ tự alphabet, class 1 = lớp đứng sau)."""
    targets = np.array(train_ds.targets)
    n_neg = (targets == 0).sum()
    n_pos = (targets == 1).sum()
    pos_weight = n_neg / max(n_pos, 1)
    return torch.tensor([pos_weight], dtype=torch.float32)