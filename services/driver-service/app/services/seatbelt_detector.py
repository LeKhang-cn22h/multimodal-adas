"""
Seatbelt Detector.

Dùng model YOLOv8m (seatbelt_yolov8m) — model đa lớp, phát hiện nhiều
hành vi/đối tượng cùng lúc:
    cell phone, drinking, eyeglass, hands off, hands on, mask, seat belt

QUAN TRỌNG: model KHÔNG có class "no_seatbelt" riêng. Logic đúng là:
    - CÓ đeo seatbelt  <=> class "seat belt" xuất hiện trong frame
    - KHÔNG đeo seatbelt <=> class "seat belt" KHÔNG xuất hiện trong frame

Vì model đa lớp, 1 frame có thể detect được nhiều class cùng lúc
(ví dụ vừa "seat belt" vừa "hands on" vừa "drinking"), nên phải kiểm
tra sự CÓ MẶT của class "seat belt" trong toàn bộ box, không phải so
sánh confidence giữa các class với nhau.

Yêu cầu: pip install ultralytics
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from ultralytics import YOLO

SEATBELT_CLASS_NAME = "seat belt"  # đúng tên class trong model, có khoảng trắng


class SeatbeltDetector:

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.3,  # khớp CONFIDENCE_THRESHOLD gốc = 0.3
    ) -> None:

        self.model = YOLO(str(model_path))
        self.confidence_threshold = confidence_threshold

        self.class_names: dict[int, str] = dict(self.model.names)

        self.seatbelt_class_id: int | None = None
        for cls_id, name in self.class_names.items():
            if name.lower() == SEATBELT_CLASS_NAME:
                self.seatbelt_class_id = cls_id
                break

        if self.seatbelt_class_id is None:
            raise ValueError(
                f"Không tìm thấy class '{SEATBELT_CLASS_NAME}' trong model. "
                f"Các class hiện có: {self.class_names}"
            )

    def detect(self, frame: np.ndarray) -> dict:
        """
        Trả về:
        {
            "has_seatbelt": bool,          # True nếu class 'seat belt' xuất hiện trong frame
            "seatbelt_confidence": float | None,
            "boxes": list[dict],           # TẤT CẢ box detect được (mọi class), để vẽ overlay
            "detected_labels": list[str],   # danh sách tên class detect được trong frame này
        }
        """

        results = self.model.predict(
            frame,
            conf=self.confidence_threshold,
            verbose=False,
        )

        boxes_out = []
        detected_labels = []
        seatbelt_confidence = None
        has_seatbelt = False

        if len(results) > 0:
            result = results[0]

            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                label = self.class_names.get(cls_id, str(cls_id))
                xyxy = box.xyxy[0].tolist()

                boxes_out.append({
                    "label": label,
                    "confidence": conf,
                    "box": xyxy,
                })

                detected_labels.append(label)

                if cls_id == self.seatbelt_class_id:
                    has_seatbelt = True
                    if seatbelt_confidence is None or conf > seatbelt_confidence:
                        seatbelt_confidence = conf

        return {
            "has_seatbelt": has_seatbelt,
            "seatbelt_confidence": seatbelt_confidence,
            "boxes": boxes_out,
            "detected_labels": detected_labels,
        }