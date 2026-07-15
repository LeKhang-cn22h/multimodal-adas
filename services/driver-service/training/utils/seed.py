"""Cố định seed cho toàn bộ random/numpy/torch — đảm bảo kết quả
train có thể tái lập giữa các lần chạy."""

import random

import numpy as np
import torch


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)