"""Lưu / tải checkpoint model (.pt state_dict)."""

from pathlib import Path

import torch
import torch.nn as nn


def save_checkpoint(model: nn.Module, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)
    print(f"Đã lưu checkpoint: {path}")


def load_checkpoint(model: nn.Module, path: Path, device: torch.device) -> nn.Module:
    state = torch.load(path, map_location=device)
    model.load_state_dict(state)
    model.to(device)
    return model