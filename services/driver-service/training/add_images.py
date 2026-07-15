"""Add new images to the dataset — GUI version (no CLI args needed).

Just run:
    python training/add_images.py

Opens a small window where you pick Subject / Glasses / Scenario, then
either:
    - "Mo Webcam"          -> live capture window (SPACE=chup 1 anh,
                               c=auto-capture lien tuc, q/ESC=thoat)
    - "Import tu thu muc"  -> pick a folder, copies+renames every image
                               inside it into the right dataset folder

Naming convention (unchanged):
    {subject}_{glasses}_{scenario}_{frameNumber}_{labelStr}.jpg

Folder mapping:
    scenario in (sleepyCombination, yawning, slowBlinkWithNodding)
        -> dataset/Multi class/train/drowsy/{scenario}/   label=drowsy
    scenario == nonsleepyCombination
        -> dataset/Multi class/train/notdrowsy/           label=notdrowsy
           (flat folder, no scenario sub-folder, matches original
           NTHU-DDD layout)
"""

import shutil
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2

DATASET_ROOT = Path("dataset/Multi class/train")
DROWSY_SCENARIOS = ["sleepyCombination", "yawning", "slowBlinkWithNodding"]
ALL_SCENARIOS = DROWSY_SCENARIOS + ["nonsleepyCombination"]
GLASSES_OPTIONS = ["noglasses", "glasses", "sunglasses", "nightglasses"]
VALID_IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp"}
AUTO_CAPTURE_INTERVAL_SEC = 0.15


# =========================================================================
# Core naming / folder logic (same rules as before, reused everywhere)
# =========================================================================


def scenario_to_label(scenario: str) -> str:
    return "notdrowsy" if scenario == "nonsleepyCombination" else "drowsy"


def target_dir(scenario: str) -> Path:
    label = scenario_to_label(scenario)
    if label == "notdrowsy":
        return DATASET_ROOT / "notdrowsy"
    return DATASET_ROOT / "drowsy" / scenario


def next_frame_number(subject: str, glasses: str, scenario: str) -> int:
    label = scenario_to_label(scenario)
    folder = target_dir(scenario)
    if not folder.is_dir():
        return 0
    pattern = f"{subject}_{glasses}_{scenario}_*_{label}.jpg"
    max_frame = -1
    for f in folder.glob(pattern):
        parts = f.stem.split("_")
        try:
            max_frame = max(max_frame, int(parts[-2]))
        except (ValueError, IndexError):
            continue
    return max_frame + 1


def count_existing(subject: str, glasses: str, scenario: str) -> int:
    label = scenario_to_label(scenario)
    folder = target_dir(scenario)
    if not folder.is_dir():
        return 0
    pattern = f"{subject}_{glasses}_{scenario}_*_{label}.jpg"
    return len(list(folder.glob(pattern)))


def build_filename(subject: str, glasses: str, scenario: str, frame_number: int) -> str:
    label = scenario_to_label(scenario)
    return f"{subject}_{glasses}_{scenario}_{frame_number}_{label}.jpg"


def known_subjects() -> list[str]:
    """Scan dataset for existing subject_ids, so the dropdown isn't empty."""
    found = set()
    if DATASET_ROOT.is_dir():
        for f in DATASET_ROOT.rglob("*.jpg"):
            parts = f.stem.split("_")
            if parts:
                found.add(parts[0])
    return sorted(found) or ["001"]


# =========================================================================
# Webcam capture (blocking OpenCV window, launched from the GUI)
# =========================================================================


def run_webcam_capture(subject: str, glasses: str, scenario: str, camera_index: int = 0) -> int:
    dst_dir = target_dir(scenario)
    dst_dir.mkdir(parents=True, exist_ok=True)
    frame_num = next_frame_number(subject, glasses, scenario)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        messagebox.showerror("Loi", f"Khong mo duoc webcam (index={camera_index}).")
        return 0

    auto_capture = False
    last_capture_time = 0.0
    captured_count = 0
    label = scenario_to_label(scenario)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        display = frame.copy()
        status = "AUTO-CAPTURE: ON" if auto_capture else "AUTO-CAPTURE: OFF"
        color = (0, 0, 255) if auto_capture else (0, 200, 0)
        cv2.putText(display, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(
            display, f"Subject={subject} Glasses={glasses} Scenario={scenario} Label={label}",
            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
        )
        cv2.putText(
            display, f"Da chup: {captured_count}  |  Frame tiep theo: {frame_num}",
            (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
        )
        cv2.putText(
            display, "SPACE=chup  c=auto  q/ESC=thoat",
            (10, display.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1,
        )
        cv2.imshow("Add Images - Webcam Capture", display)

        key = cv2.waitKey(1) & 0xFF
        do_capture = key == ord(" ")
        if key == ord("c"):
            auto_capture = not auto_capture
        elif key in (ord("q"), 27):
            break

        if auto_capture and (time.time() - last_capture_time) >= AUTO_CAPTURE_INTERVAL_SEC:
            do_capture = True

        if do_capture:
            filename = build_filename(subject, glasses, scenario, frame_num)
            cv2.imwrite(str(dst_dir / filename), frame)
            frame_num += 1
            captured_count += 1
            last_capture_time = time.time()

    cap.release()
    cv2.destroyAllWindows()
    return captured_count


# =========================================================================
# Import from folder
# =========================================================================


def run_import(subject: str, glasses: str, scenario: str, source_dir: Path) -> tuple[int, int]:
    dst_dir = target_dir(scenario)
    dst_dir.mkdir(parents=True, exist_ok=True)
    frame_num = next_frame_number(subject, glasses, scenario)

    images = sorted(p for p in source_dir.iterdir() if p.suffix.lower() in VALID_IMG_EXT)
    copied, skipped = 0, 0

    for src_path in images:
        new_name = build_filename(subject, glasses, scenario, frame_num)
        dst_path = dst_dir / new_name
        if src_path.suffix.lower() == ".jpg":
            shutil.copy2(src_path, dst_path)
        else:
            img = cv2.imread(str(src_path))
            if img is None:
                skipped += 1
                continue
            cv2.imwrite(str(dst_path), img)
        frame_num += 1
        copied += 1

    return copied, skipped


# =========================================================================
# GUI
# =========================================================================


class AddImagesApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Them anh vao Dataset - Drowsiness Detection")
        root.geometry("440x360")
        root.resizable(False, False)

        pad = {"padx": 12, "pady": 6}

        # Subject
        tk.Label(root, text="Subject ID:").grid(row=0, column=0, sticky="w", **pad)
        self.subject_var = tk.StringVar()
        self.subject_combo = ttk.Combobox(
            root, textvariable=self.subject_var, values=known_subjects(), width=25,
        )
        self.subject_combo.grid(row=0, column=1, **pad)
        if known_subjects():
            self.subject_combo.set(known_subjects()[-1])

        # Glasses
        tk.Label(root, text="Glasses:").grid(row=1, column=0, sticky="w", **pad)
        self.glasses_var = tk.StringVar(value=GLASSES_OPTIONS[0])
        self.glasses_combo = ttk.Combobox(
            root, textvariable=self.glasses_var, values=GLASSES_OPTIONS, width=25,
        )
        self.glasses_combo.grid(row=1, column=1, **pad)

        # Scenario
        tk.Label(root, text="Scenario:").grid(row=2, column=0, sticky="w", **pad)
        self.scenario_var = tk.StringVar(value=ALL_SCENARIOS[0])
        self.scenario_combo = ttk.Combobox(
            root, textvariable=self.scenario_var, values=ALL_SCENARIOS, width=25, state="readonly",
        )
        self.scenario_combo.grid(row=2, column=1, **pad)
        self.scenario_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_info())

        # Derived label + existing count (read-only info)
        self.info_var = tk.StringVar()
        tk.Label(root, textvariable=self.info_var, fg="gray20", justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 10),
        )

        ttk.Separator(root, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", padx=12)

        # Buttons
        tk.Button(
            root, text="Mo Webcam", font=("Segoe UI", 11), bg="#2e7d32", fg="white",
            width=25, height=2, command=self.on_webcam,
        ).grid(row=5, column=0, columnspan=2, pady=(16, 6))

        tk.Button(
            root, text="Import tu thu muc", font=("Segoe UI", 11), bg="#1565c0", fg="white",
            width=25, height=2, command=self.on_import,
        ).grid(row=6, column=0, columnspan=2, pady=6)

        # Status bar
        self.status_var = tk.StringVar(value="San sang.")
        tk.Label(root, textvariable=self.status_var, fg="gray30", anchor="w").grid(
            row=7, column=0, columnspan=2, sticky="ew", padx=12, pady=(14, 0),
        )

        for widget in (self.subject_combo, self.glasses_combo):
            widget.bind("<KeyRelease>", lambda e: self.refresh_info())
            widget.bind("<<ComboboxSelected>>", lambda e: self.refresh_info())

        self.refresh_info()

    def current_params(self) -> tuple[str, str, str]:
        subject = self.subject_var.get().strip()
        glasses = self.glasses_var.get().strip()
        scenario = self.scenario_var.get().strip()
        return subject, glasses, scenario

    def refresh_info(self) -> None:
        subject, glasses, scenario = self.current_params()
        if not subject or not glasses:
            self.info_var.set("Nhap Subject va Glasses de xem thong tin.")
            return
        label = scenario_to_label(scenario)
        n_existing = count_existing(subject, glasses, scenario)
        next_frame = next_frame_number(subject, glasses, scenario)
        folder = target_dir(scenario)
        self.info_var.set(
            f"Nhan: {label}   |   Da co: {n_existing} anh   |   Frame tiep theo: {next_frame}\n"
            f"Thu muc dich: {folder}"
        )

    def validate(self) -> tuple[str, str, str] | None:
        subject, glasses, scenario = self.current_params()
        if not subject:
            messagebox.showwarning("Thieu thong tin", "Vui long nhap Subject ID.")
            return None
        if not glasses:
            messagebox.showwarning("Thieu thong tin", "Vui long nhap/chon Glasses.")
            return None
        return subject, glasses, scenario

    def on_webcam(self) -> None:
        params = self.validate()
        if not params:
            return
        subject, glasses, scenario = params
        self.status_var.set("Dang mo webcam... (dong cua so webcam de quay lai)")
        self.root.update()
        count = run_webcam_capture(subject, glasses, scenario)
        self.status_var.set(f"Da chup {count} anh.")
        self.refresh_info()

    def on_import(self) -> None:
        params = self.validate()
        if not params:
            return
        subject, glasses, scenario = params

        source = filedialog.askdirectory(title="Chon thu muc chua anh can import")
        if not source:
            return
        source_dir = Path(source)

        copied, skipped = run_import(subject, glasses, scenario, source_dir)
        msg = f"Da import {copied} anh."
        if skipped:
            msg += f" ({skipped} anh bi bo qua do loi doc file)"
        self.status_var.set(msg)
        messagebox.showinfo("Hoan tat", msg)
        self.refresh_info()


def main() -> None:
    root = tk.Tk()
    AddImagesApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()