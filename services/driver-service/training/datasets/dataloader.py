"""DataLoader dùng chung — build từ 1 thư mục ImageFolder chuẩn
(train/{class}/, val/{class}/), tái sử dụng cho cả eye và mouth."""

from pathlib import Path

from torch.utils.data import DataLoader
from torchvision import datasets

from datasets.transforms import build_train_transform, build_val_transform


def build_dataloaders(
    data_dir: Path,
    img_size: int,
    batch_size: int,
    num_workers: int = 4,
) -> tuple[DataLoader, DataLoader, datasets.ImageFolder, datasets.ImageFolder]:
    """Trả về (train_loader, val_loader, train_dataset, val_dataset).
    Giữ lại 2 dataset gốc vì train.py cần dùng train_ds.targets để
    tính pos_weight và train_ds.class_to_idx để log."""
    train_tf = build_train_transform(img_size)
    val_tf = build_val_transform(img_size)

    train_ds = datasets.ImageFolder(data_dir / "train", transform=train_tf)
    val_ds = datasets.ImageFolder(data_dir / "val", transform=val_tf)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True,
        persistent_workers=num_workers > 0,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True,
        persistent_workers=num_workers > 0,
    )
    return train_loader, val_loader, train_ds, val_ds