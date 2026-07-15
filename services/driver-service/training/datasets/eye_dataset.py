"""Wrapper dataset riêng cho task eye — chỉ truyền config vào
dataloader.py dùng chung, giữ file riêng để dễ tuỳ biến logic đọc data
riêng cho eye sau này nếu cần (VD lọc thêm theo điều kiện ánh sáng)."""

from configs.eye_config import EyeConfig
from datasets.dataloader import build_dataloaders


def get_eye_dataloaders(cfg: EyeConfig):
    return build_dataloaders(
        data_dir=cfg.data_dir,
        img_size=cfg.img_size,
        batch_size=cfg.batch_size,
        num_workers=cfg.num_workers,
    )