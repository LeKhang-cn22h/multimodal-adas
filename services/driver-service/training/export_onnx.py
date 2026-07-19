"""Export 1 checkpoint .pt đã train sang .onnx (nhẹ hơn, dùng để
deploy/inference nhanh trên thiết bị thật).

Chạy:
    python training/export_onnx.py --task eye
    python training/export_onnx.py --task mouth --checkpoint path/to/other.pt
"""

import argparse

import torch

from configs.eye_config import EyeConfig
from configs.mouth_config import MouthConfig
from models.eye_cnn import build_eye_model
from models.mouth_cnn import build_mouth_model
from utils.checkpoint import load_checkpoint

CONFIGS = {"eye": EyeConfig, "mouth": MouthConfig}
MODELS = {"eye": build_eye_model, "mouth": build_mouth_model}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["eye", "mouth"], required=True)
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    cfg = CONFIGS[args.task]()
    checkpoint_path = args.checkpoint or cfg.model_path_pt
    output_path = args.output or cfg.model_path_onnx

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MODELS[args.task](device)
    model = load_checkpoint(model, checkpoint_path, device)
    model.eval()

    dummy = torch.randn(1, 3, cfg.img_size, cfg.img_size, device=device)
    torch.onnx.export(
        model, dummy, str(output_path),
        input_names=["input"], output_names=["logit"],
        dynamic_axes={"input": {0: "batch"}, "logit": {0: "batch"}},
        opset_version=13,
    )

    pt_size = checkpoint_path.stat().st_size / 1024 if hasattr(checkpoint_path, "stat") else 0
    onnx_size = output_path.stat().st_size / 1024
    print(f"Đã export: {output_path}")
    print(f".pt: {pt_size:.1f} KB  ->  .onnx: {onnx_size:.1f} KB")


if __name__ == "__main__":
    main()