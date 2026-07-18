"""EarlyStopping — theo dõi 1 metric (VD val_auc), dừng train nếu
không cải thiện sau `patience` epoch, tự lưu lại state tốt nhất."""

import copy

import torch.nn as nn


class EarlyStopping:
    def __init__(self, patience: int = 4, mode: str = "max") -> None:
        self.patience = patience
        self.mode = mode
        self.best_score: float | None = None
        self.counter = 0
        self.best_state: dict | None = None
        self.should_stop = False

    def step(self, score: float, model: nn.Module) -> bool:
        """Gọi sau mỗi epoch. Trả về True nếu score này là tốt nhất
        từ trước đến giờ (đã lưu lại state)."""
        improved = (
            self.best_score is None
            or (score > self.best_score if self.mode == "max" else score < self.best_score)
        )
        if improved:
            self.best_score = score
            self.best_state = copy.deepcopy(model.state_dict())
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        return improved

    def restore_best(self, model: nn.Module) -> None:
        if self.best_state is not None:
            model.load_state_dict(self.best_state)