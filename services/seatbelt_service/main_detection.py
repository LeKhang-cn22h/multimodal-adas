"""
Test YOLO Detection model (seatbelt_detection5/weights/best.pt).
Classes: drinking, eyeglass, hands off, hands on, mask, seatbelt
Seatbelt Detection - YOLOv8m (seatbelt_yolov8m)

Classes: cell phone, drinking, eyeglass, hands off, hands on, mask, seatbelt

Pipeline:
  1. Chon video file tu may local (tkinter dialog hoac CLI --input).
  2. Chay YOLOv8m detection tren tung frame.
  3. Ve bounding box + label + confidence + FPS.
  4. Canh bao neu khong co class 'seatbelt' (sau N frame lien tiep).
"""

import argparse
import os
import time
from collections import Counter
from tkinter import Tk, filedialog

import cv2
import numpy as np
from ultralytics import YOLO

# ---------------------------------------------------------------------------
# Hang so
# ---------------------------------------------------------------------------
DEFAULT_DETECTION_MODEL = r"app/seatbelt_yolov8m/weights/best.pt"
CONFIDENCE_THRESHOLD = 0.3
WARNING_FRAME_THRESHOLD = 10  # so frame lien tiep khong co seatbelt -> WARNING

# Classes tu model (dynamic - se override sau khi load model)
CLASS_NAMES = {}
SEATBELT_CLASS_ID = None

# Mau sac cho tung class (BGR) - su dung palette linh hoat
CLASS_COLORS = {
    0: (0, 0, 255),     # no seat belt - do
    1: (0, 255, 0),     # seat belt - xanh la
}

GREEN  = (0, 255, 0)
RED    = (0, 0, 255)
WHITE  = (255, 255, 255)
BLACK  = (0, 0, 0)


# ---------------------------------------------------------------------------
# Util
# ---------------------------------------------------------------------------

def put_text_with_bg(frame, text, pos, font_scale=0.55, thickness=2, color=WHITE, bg=BLACK):
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    x, y = pos
    cv2.rectangle(frame, (x, y - th - 4), (x + tw + 6, y + baseline), bg, -1)
    cv2.putText(frame, text, (x + 3, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)


def draw_detections(frame, results, conf_threshold):
    """Ve tat ca detections len frame, tra ve list class_ids detected."""
    boxes_data = results[0].boxes
    detected_classes = []

    if boxes_data is None or len(boxes_data) == 0:
        return frame, detected_classes

    for box in boxes_data:
        conf = float(box.conf[0])
        if conf < conf_threshold:
            continue

        cls_id = int(box.cls[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        label = CLASS_NAMES.get(cls_id, str(cls_id))
        color = CLASS_COLORS.get(cls_id, WHITE)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        put_text_with_bg(frame, f"{label} {conf:.2f}", (x1, y1 - 5), color=color)
        detected_classes.append(cls_id)

    return frame, detected_classes


def draw_status_overlay(frame, no_seatbelt_count, threshold, has_seatbelt, current_fps, detected_classes):
    """Ve trang thai canh bao o goc tren trai."""
    h, w = frame.shape[:2]

    if has_seatbelt:
        status_text = "SEATBELT: OK"
        bg_color = (0, 120, 0)
    elif no_seatbelt_count >= threshold:
        status_text = f"WARNING: NO SEATBELT ({no_seatbelt_count}f)"
        bg_color = (0, 0, 180)
    else:
        status_text = f"No seatbelt ({no_seatbelt_count}/{threshold})"
        bg_color = (0, 100, 180)

    (tw, th), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    cv2.rectangle(frame, (10, 10), (20 + tw, 20 + th + 6), bg_color, -1)
    cv2.putText(frame, status_text, (15, 10 + th + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 2)

    # FPS counter (goc tren phai)
    fps_text = f"FPS: {current_fps:.1f}"
    (ftw, fth), _ = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    cv2.rectangle(frame, (w - ftw - 20, 10), (w - 5, 18 + fth + 6), (40, 40, 40), -1)
    cv2.putText(frame, fps_text, (w - ftw - 14, 10 + fth + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 2)

    # Detected classes (goc duoi trai)
    if detected_classes:
        class_names = [CLASS_NAMES.get(c, str(c)) for c in detected_classes]
        det_text = "Detected: " + ", ".join(class_names)
        if len(det_text) > 60:
            det_text = det_text[:57] + "..."
        put_text_with_bg(frame, det_text, (10, h - 35), font_scale=0.45, color=(200, 200, 200))

    return frame


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def process_video(
    input_path: str,
    output_path=None,
    model_path: str = DEFAULT_DETECTION_MODEL,
    conf_threshold: float = CONFIDENCE_THRESHOLD,
    warning_threshold: int = WARNING_FRAME_THRESHOLD,
    display: bool = True,
    flip: bool = False,
):
    print("=" * 60)
    print(f"[INFO] Loading model: {model_path}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Khong tim thay model: {model_path}")

    model = YOLO(model_path)
    print(f"[OK]   Model ready. Classes: {model.names}")

    # ── Cap nhat CLASS_NAMES va SEATBELT_CLASS_ID tu model ──────────
    global CLASS_NAMES, SEATBELT_CLASS_ID
    CLASS_NAMES = dict(model.names)
    # Tim class "seat belt" (exact match, case-insensitive)
    for cls_id, name in CLASS_NAMES.items():
        if name.lower() == "seat belt":
            SEATBELT_CLASS_ID = cls_id
            break
    print(f"[INFO] SEATBELT_CLASS_ID = {SEATBELT_CLASS_ID}")

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Khong mo duoc video: {input_path}")

    fps    = cap.get(cv2.CAP_PROP_FPS) or 30
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[INFO] {width}x{height} @ {fps:.1f}fps, {total} frames")

    out = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if display:
        cv2.namedWindow("Detection Test", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Detection Test", min(width, 1280), min(height, 720))

    no_seatbelt_count = 0
    frame_count = 0
    paused = False

    # ── FPS + stats tracking ─────────────────────────────────────
    fps_start = time.time()
    fps_frame_count = 0
    current_fps = 0.0
    detection_counter = Counter()  # dem so lan xuat hien tung class

    print("=" * 60)
    print("[INFO] Nhan 'q' de thoat, 'p' de tam dung/tiep tuc.")

    try:
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    break

                if flip:
                    frame = cv2.flip(frame, 1)

                frame_count += 1

                # --- Inference ---
                results = model(frame, conf=conf_threshold, verbose=False)
                frame, detected_classes = draw_detections(frame, results, conf_threshold)

                # --- Cap nhat stats ---
                for c in detected_classes:
                    detection_counter[c] += 1

                # --- Logic canh bao: khong co seatbelt ---
                has_seatbelt = SEATBELT_CLASS_ID in detected_classes
                if has_seatbelt:
                    no_seatbelt_count = 0
                else:
                    no_seatbelt_count += 1

                # --- FPS (5s sliding window) ---
                fps_frame_count += 1
                elapsed_fps = time.time() - fps_start
                if elapsed_fps >= 2.0:
                    current_fps = fps_frame_count / elapsed_fps
                    fps_frame_count = 0
                    fps_start = time.time()

                frame = draw_status_overlay(frame, no_seatbelt_count, warning_threshold,
                                            has_seatbelt, current_fps, detected_classes)

                # --- Frame counter ---
                put_text_with_bg(frame, f"Frame: {frame_count}/{total}", (10, height - 15),
                                 font_scale=0.5, color=(200, 200, 200))

                if out:
                    out.write(frame)

                if frame_count % 60 == 0:
                    pct = (frame_count / total * 100) if total else 0
                    print(f"  Frame {frame_count}/{total} ({pct:.1f}%) | seatbelt={has_seatbelt} | "
                          f"no_sb={no_seatbelt_count} | fps={current_fps:.1f}")

            if display:
                cv2.imshow("Detection Test", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("\n[INFO] Thoat boi nguoi dung.")
                    break
                elif key == ord("p"):
                    paused = not paused
                    print("[INFO]", "Tam dung." if paused else "Tiep tuc.")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted.")
    finally:
        cap.release()
        if out:
            out.release()
        cv2.destroyAllWindows()

    print("=" * 60)
    print(f"[DONE] {frame_count} frames processed.")
    if detection_counter:
        print(f"[STATS] Detection summary:")
        total_detections = sum(detection_counter.values())
        for cls_id in sorted(detection_counter.keys()):
            name = CLASS_NAMES.get(cls_id, str(cls_id))
            count = detection_counter[cls_id]
            pct = count / total_detections * 100 if total_detections else 0
            print(f"  {name:15s}: {count:6d}  ({pct:5.1f}%)")
        seatbelt_frames = frame_count - (detection_counter.get(0, 0) > 0 and frame_count or 0)
        print(f"  {'seatbelt OK':15s}: {frame_count - no_seatbelt_count:6d}  (deduced)")
    if output_path:
        print(f"[DONE] Output: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def select_video_file() -> str:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Chon video",
        filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.webm *.wmv *.flv"), ("All files", "*.*")],
    )
    root.destroy()
    if not path:
        print("[INFO] Khong chon file. Thoat.")
        exit(0)
    return path


def main():
    parser = argparse.ArgumentParser(description="Seatbelt Detection — YOLOv8m (seatbelt_yolov8m)")
    parser.add_argument("-i", "--input",  default=None, help="Duong dan video dau vao.")
    parser.add_argument("-o", "--output", default=None, help="Duong dan video dau ra.")
    parser.add_argument("--model",  default=DEFAULT_DETECTION_MODEL, help="Duong dan model .pt.")
    parser.add_argument("--conf",   type=float, default=CONFIDENCE_THRESHOLD, help="Nguong conf (default 0.3).")
    parser.add_argument("--warn",   type=int,   default=WARNING_FRAME_THRESHOLD, help="So frame canh bao (default 10).")
    parser.add_argument("--no-display", action="store_true", help="Khong hien thi realtime.")
    parser.add_argument("--flip",        action="store_true", help="Flip ngang video.")
    args = parser.parse_args()

    input_path = args.input or select_video_file()

    process_video(
        input_path=input_path,
        output_path=args.output,
        model_path=args.model,
        conf_threshold=args.conf,
        warning_threshold=args.warn,
        display=not args.no_display,
        flip=args.flip,
    )


if __name__ == "__main__":
    main()