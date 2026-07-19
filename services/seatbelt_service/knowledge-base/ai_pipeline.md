# AI Pipeline - Seatbelt-Service

## Vị trí trong pipeline

Seatbelt-Service nằm ở tầng AI, sau Camera-Service và trước hiển thị kết quả.

## Model

- **Framework**: Ultralytics YOLO
- **Model file**: `best_1.pt`
- **Classes**: 7 (cell phone, drinking, eyeglass, hands off, hands on, mask, seatbelt)
- **Target class**: `class_id=6` (seatbelt)

## Inference flow

```
JPEG bytes → cv2.imdecode → BGR numpy → YOLO model(frame, conf=0.3) → boxes → filter seatbelt (class_id=6)
```

## Logic sau inference

```
has_seatbelt = any(box.cls == 6 for box in boxes)
if has_seatbelt: streak = 0
else: streak += 1
warning = streak >= WARNING_FRAMES
```

## KHÔNG thực hiện

- KHÔNG vẽ bounding box.
- KHÔNG gửi ảnh qua RabbitMQ (chỉ JSON).
- KHÔNG retrain model.
- KHÔNG thay đổi confidence threshold logic.
