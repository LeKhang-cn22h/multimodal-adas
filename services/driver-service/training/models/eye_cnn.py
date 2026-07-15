"""Model riêng cho task eye — hiện dùng chung kiến trúc MobileNetV2 ở
common.py. Giữ file riêng để dễ đổi kiến trúc khác cho eye sau này mà
không ảnh hưởng tới mouth."""

import torch
import torch.nn as nn

from training.models.common import build_mobilenet_classifier


def build_eye_model(device: torch.device) -> nn.Module:
    return build_mobilenet_classifier(device)