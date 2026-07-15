"""Wrapper dataset riêng cho task mouth — chỉ truyền config vào
dataloader.py dùng chung, giữ file riêng để dễ tuỳ biến logic đọc data
riêng cho mouth sau này nếu cần."""

from configs.mouth_config import MouthConfig
from datasets.dataloader import build_dataloaders


def get_mouth_dataloaders(cfg: MouthConfig):
    return build_dataloaders(
        data_dir=cfg.data_dir,
        img_size=cfg.img_size,
        batch_size=cfg.batch_size,
        num_workers=cfg.num_workers,
    )