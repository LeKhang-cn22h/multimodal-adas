"""Trainer — đóng gói vòng lặp train/eval 1 epoch, và orchestrate
2 giai đoạn (freeze backbone -> fine-tune top layers), có early
stopping + mixed precision (AMP) tự động nếu chạy trên GPU."""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from models.common import unfreeze_top_layers
from utils.early_stopping import EarlyStopping
from utils.metrics import compute_metrics


class Trainer:
    def __init__(
        self,
        model: nn.Module,
        device: torch.device,
        pos_weight: torch.Tensor,
        patience: int = 4,
        use_amp: bool | None = None,
    ) -> None:
        self.model = model
        self.device = device
        self.criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        self.patience = patience
        self.use_amp = (device.type == "cuda") if use_amp is None else use_amp
        self.scaler = torch.cuda.amp.GradScaler() if self.use_amp else None

    def _run_epoch(self, loader: DataLoader, optimizer, train: bool) -> dict:
        self.model.train() if train else self.model.eval()

        total_loss = 0.0
        all_targets: list[float] = []
        all_probs: list[float] = []

        context = torch.enable_grad() if train else torch.no_grad()
        with context:
            for images, labels in loader:
                images = images.to(self.device, non_blocking=True)
                labels = labels.float().unsqueeze(1).to(self.device, non_blocking=True)

                if train:
                    optimizer.zero_grad()

                if self.scaler is not None:
                    with torch.autocast(device_type="cuda", dtype=torch.float16):
                        logits = self.model(images)
                        loss = self.criterion(logits, labels)
                    if train:
                        self.scaler.scale(loss).backward()
                        self.scaler.step(optimizer)
                        self.scaler.update()
                else:
                    logits = self.model(images)
                    loss = self.criterion(logits, labels)
                    if train:
                        loss.backward()
                        optimizer.step()

                total_loss += loss.item() * images.size(0)
                probs = torch.sigmoid(logits.detach()).cpu().numpy().ravel()
                all_probs.extend(probs.tolist())
                all_targets.extend(labels.detach().cpu().numpy().ravel().tolist())

        avg_loss = total_loss / len(loader.dataset)
        y_true = np.array(all_targets, dtype=int)
        y_proba = np.array(all_probs)
        y_pred = (y_proba >= 0.5).astype(int)

        m = compute_metrics(y_true, y_pred, y_proba)
        return {"loss": avg_loss, "accuracy": m["accuracy"], "auc": m["auc"], "recall": m["recall"]}

    def evaluate(self, loader: DataLoader) -> tuple[dict, np.ndarray, np.ndarray, np.ndarray]:
        """Đánh giá đầy đủ, trả kèm y_true/y_pred/y_proba để vẽ biểu
        đồ confusion matrix / ROC bên ngoài."""
        self.model.eval()
        all_targets, all_probs = [], []
        with torch.no_grad():
            for images, labels in loader:
                images = images.to(self.device, non_blocking=True)
                logits = self.model(images)
                probs = torch.sigmoid(logits).cpu().numpy().ravel()
                all_probs.extend(probs.tolist())
                all_targets.extend(labels.numpy().ravel().tolist())

        y_true = np.array(all_targets, dtype=int)
        y_proba = np.array(all_probs)
        y_pred = (y_proba >= 0.5).astype(int)
        metrics = compute_metrics(y_true, y_pred, y_proba)
        return metrics, y_true, y_pred, y_proba

    def _train_phase(self, train_loader, val_loader, optimizer, epochs: int) -> dict:
        history: dict = {}
        stopper = EarlyStopping(patience=self.patience, mode="max")

        for epoch in range(1, epochs + 1):
            train_m = self._run_epoch(train_loader, optimizer, train=True)
            val_m = self._run_epoch(val_loader, optimizer, train=False)

            for k, v in train_m.items():
                history.setdefault(k, []).append(v)
            for k, v in val_m.items():
                history.setdefault(f"val_{k}", []).append(v)

            print(
                f"  Epoch {epoch}/{epochs} — "
                f"loss={train_m['loss']:.4f} acc={train_m['accuracy']:.4f} auc={train_m['auc']:.4f} | "
                f"val_loss={val_m['loss']:.4f} val_acc={val_m['accuracy']:.4f} val_auc={val_m['auc']:.4f}"
            )

            stopper.step(val_m["auc"], self.model)
            if stopper.should_stop:
                print(f"  Early stopping (val_auc không cải thiện sau {self.patience} epoch)")
                break

        stopper.restore_best(self.model)
        return history

    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epochs_head: int,
        epochs_finetune: int,
        lr_head: float,
        lr_finetune: float,
        unfreeze_last_n: int = 30,
    ) -> tuple[dict, dict]:
        """Chạy đủ 2 giai đoạn, trả về (history_giai_đoạn_1, history_giai_đoạn_2)."""
        print("Giai đoạn 1: train head (backbone đóng băng)")
        optimizer = torch.optim.Adam(
            filter(lambda p: p.requires_grad, self.model.parameters()), lr=lr_head,
        )
        history1 = self._train_phase(train_loader, val_loader, optimizer, epochs_head)

        print("\nGiai đoạn 2: fine-tune (mở khoá layer cuối backbone)")
        unfreeze_top_layers(self.model, n_layers=unfreeze_last_n)
        optimizer = torch.optim.Adam(
            filter(lambda p: p.requires_grad, self.model.parameters()), lr=lr_finetune,
        )
        history2 = self._train_phase(train_loader, val_loader, optimizer, epochs_finetune)

        return history1, history2