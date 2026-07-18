"""
Image preprocessing dùng chung cho Eye CNN và Mouth CNN.

Pipeline phải giống hệt lúc train:

Resize
↓
ToTensor
↓
Normalize(ImageNet)
"""

from __future__ import annotations

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import transforms


class ImagePreprocessor:
    """
    Chuẩn hóa ROI trước khi đưa vào CNN.

    Input:
        - OpenCV BGR image (numpy.ndarray)
        - PIL.Image

    Output:
        Tensor shape:
            (1, 3, H, W)
    """

    def __init__(self, image_size: int) -> None:

        self.transform = transforms.Compose(
            [
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )

    def _to_pil(
        self,
        image: np.ndarray | Image.Image,
    ) -> Image.Image:

        if isinstance(image, Image.Image):
            return image

        if not isinstance(image, np.ndarray):
            raise TypeError(
                "image phải là numpy.ndarray hoặc PIL.Image"
            )

        rgb = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB,
        )

        return Image.fromarray(rgb)

    def preprocess(
        self,
        image: np.ndarray | Image.Image,
    ) -> torch.Tensor:

        image = self._to_pil(image)

        tensor = self.transform(image)

        return tensor.unsqueeze(0)

    def __call__(
        self,
        image: np.ndarray | Image.Image,
    ) -> torch.Tensor:

        return self.preprocess(image)