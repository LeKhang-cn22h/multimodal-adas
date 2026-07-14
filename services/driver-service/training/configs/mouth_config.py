"""Config cho task mouth-state (ngáp/không ngáp)."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MouthConfig:
    task_name: str = "mouth"
    data_dir: Path = Path("training/output/cnn_data/mouth_state")
    classes: list[str] = field(default_factory=lambda: ["no_yawn", "yawn"])

    # Data
    img_size: int = 96
    batch_size: int = 32
    num_workers: int = 4

    # Training
    epochs_head: int = 15
    epochs_finetune: int = 8
    lr_head: float = 1e-3
    lr_finetune: float = 1e-5
    unfreeze_last_n: int = 30
    patience: int = 4
    seed: int = 42

    # Output
    output_dir: Path = Path("training/output")

    @property
    def model_path_pt(self) -> Path:
        return self.output_dir / f"{self.task_name}_state_model.pt"

    @property
    def model_path_onnx(self) -> Path:
        return self.output_dir / f"{self.task_name}_state_model.onnx"

    @property
    def report_path(self) -> Path:
        return self.output_dir / f"cnn_{self.task_name}_report.txt"