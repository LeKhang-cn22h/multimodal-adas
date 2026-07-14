"""Model riêng cho task mouth — hiện dùng chung kiến trúc MobileNetV2
ở common.py. Giữ file riêng để dễ đổi kiến trúc khác cho mouth sau
này mà không ảnh hưởng tới eye (VD ảnh mouth nhỏ hơn, có thể cần
backbone nhẹ hơn nếu overfit)."""

import torch
import torch.nn as nn

from training.models.common import build_mobilenet_classifier


def build_mouth_model(device: torch.device) -> nn.Module:
    return build_mobilenet_classifier(device)