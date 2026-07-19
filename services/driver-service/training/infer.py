"""Inference — dự đoán trạng thái mắt/miệng cho 1 ảnh hoặc qua webcam,
dùng model .pt đã train. Đây là bước test nhanh model, CHƯA tích hợp
với MediaPipe crop tự động (ảnh đưa vào cần đã là ảnh crop mắt/miệng
sẵn, giống định dạng dữ liệu train).

Chạy:
    python training/infer.py --task eye --image path/to/eye_crop.jpg
    python training/infer.py --task mouth --webcam
"""

import argparse

import cv2
import numpy as np
import torch
from PIL import Image

from configs.eye_config import EyeConfig
from configs.mouth_config import MouthConfig
from datasets.transforms import build_val_transform
from models.eye_cnn import build_eye_model
from models.mouth_cnn import build_mouth_model
from utils.checkpoint import load_checkpoint

CONFIGS = {"eye": EyeConfig, "mouth": MouthConfig}
MODELS = {"eye": build_eye_model, "mouth": build_mouth_model}


def predict_pil(model, transform, device, pil_img: Image.Image, classes: list[str]) -> tuple[str, float]:
    tensor = transform(pil_img).unsqueeze(0).to(device)
    with torch.no_grad():
        logit = model(tensor)
        prob = torch.sigmoid(logit).item()
    label = classes[1] if prob >= 0.5 else classes[0]
    confidence = prob if prob >= 0.5 else 1 - prob
    return label, confidence


def run_image(args, cfg, model, transform, device) -> None:
    img = Image.open(args.image).convert("RGB")
    label, confidence = predict_pil(model, transform, device, img, cfg.classes)
    print(f"Ảnh: {args.image}")
    print(f"Dự đoán: {label}  (độ tin cậy: {confidence*100:.1f}%)")


def run_webcam(args, cfg, model, transform, device) -> None:
    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print("Không mở được webcam.")
        return

    print("Nhấn 'q' để thoát.")
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        label, confidence = predict_pil(model, transform, device, pil_img, cfg.classes)

        text = f"{label} ({confidence*100:.0f}%)"
        color = (0, 0, 255) if label in ("closed", "yawn") else (0, 200, 0)
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
        cv2.imshow(f"Infer - {cfg.task_name}", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["eye", "mouth"], required=True)
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument("--image", type=str, default=None, help="Đường dẫn 1 ảnh để test")
    parser.add_argument("--webcam", action="store_true", help="Dùng webcam thay vì ảnh tĩnh")
    parser.add_argument("--camera-index", type=int, default=0)
    args = parser.parse_args()

    if not args.image and not args.webcam:
        print("Cần chọn --image hoặc --webcam")
        return

    cfg = CONFIGS[args.task]()
    checkpoint_path = args.checkpoint or cfg.model_path_pt

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MODELS[args.task](device)
    model = load_checkpoint(model, checkpoint_path, device)
    model.eval()

    transform = build_val_transform(cfg.img_size)

    if args.image:
        run_image(args, cfg, model, transform, device)
    else:
        run_webcam(args, cfg, model, transform, device)


if __name__ == "__main__":
    main()