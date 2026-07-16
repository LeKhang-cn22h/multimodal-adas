"""
label_tool.py — ADAS Dataset Labeling Tool.

Standalone desktop application for labelling images with 5 attributes:
Eye, Glass, Face, Yawn, Seatbelt.  Renames images following the
naming convention: {eye}_{glass}_{face}_{yawn}_{seatbelt}_{XXXX}.ext

NEW: Import Video -> extracts frames from a video file, saves them as
.jpg images already following the naming convention above (with a
default label + sequential 4-digit index), and loads them into the
tool so you can review/relabel them right away.

Usage:
    pip install customtkinter pillow opencv-python
    python label_tool.py
"""

from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import Optional

import customtkinter as ctk
from PIL import Image

try:
    import cv2  # opencv-python
except ImportError:  # pragma: no cover
    cv2 = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS: set[str] = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}

EYE_VALUES: tuple[str, str] = ("eyeopen", "eyeclose")
GLASS_VALUES: tuple[str, str] = ("glass", "noglass")
FACE_VALUES: tuple[str, str] = ("face", "noface")
YAWN_VALUES: tuple[str, str] = ("yawn", "noyawn")
SEATBELT_VALUES: tuple[str, str] = ("seatbelt", "noseatbelt")

# Default labels applied to frames extracted from video, before the
# user reviews/relabels them individually.
DEFAULT_EYE: str = EYE_VALUES[0]
DEFAULT_GLASS: str = GLASS_VALUES[1]
DEFAULT_FACE: str = FACE_VALUES[1]
DEFAULT_YAWN: str = YAWN_VALUES[1]
DEFAULT_SEATBELT: str = SEATBELT_VALUES[1]

# Regex for parsing existing labelled filenames.
FILENAME_PATTERN: re.Pattern = re.compile(
    r"^(eyeopen|eyeclose)_(glass|noglass)_(face|noface)_"
    r"(yawn|noyawn)_(seatbelt|noseatbelt)_(\d{4})"
    r"\.(jpg|jpeg|png|bmp|webp)$",
    re.IGNORECASE,
)

# Human-readable display names for radio buttons.
LABEL_DISPLAY: dict[str, str] = {
    "eyeopen": "Eye Open",
    "eyeclose": "Eye Close",
    "glass": "Glass",
    "noglass": "No Glass",
    "face": "Face",
    "noface": "No Face",
    "yawn": "Yawn",
    "noyawn": "No Yawn",
    "seatbelt": "Seatbelt",
    "noseatbelt": "No Seatbelt",
}

# ---------------------------------------------------------------------------
# LabelTool
# ---------------------------------------------------------------------------


class LabelTool:
    """Main application window for the ADAS labelling tool."""

    def __init__(self) -> None:
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self._root: ctk.CTk = ctk.CTk()
        self._root.title("ADAS Label Tool")
        self._root.geometry("1400x900")
        self._root.minsize(900, 600)

        # ── Application state ──────────────────────────────────────────
        self._folder: Optional[Path] = None
        self._images: list[Path] = []
        self._current_index: int = 0
        self._original_image: Optional[Image.Image] = None

        # ── Label variables (bound to radio buttons) ───────────────────
        self._eye_var: tk.StringVar = tk.StringVar(value=EYE_VALUES[0])
        self._glass_var: tk.StringVar = tk.StringVar(value=GLASS_VALUES[0])
        self._face_var: tk.StringVar = tk.StringVar(value=FACE_VALUES[0])
        self._yawn_var: tk.StringVar = tk.StringVar(value=YAWN_VALUES[0])
        self._seatbelt_var: tk.StringVar = tk.StringVar(value=SEATBELT_VALUES[0])

        # Realtime preview: update whenever any label changes.
        for var in (
            self._eye_var,
            self._glass_var,
            self._face_var,
            self._yawn_var,
            self._seatbelt_var,
        ):
            var.trace_add("write", self._on_label_changed)

        # ── Build UI ───────────────────────────────────────────────────
        self._setup_ui()
        self._bind_keys()

    # =====================================================================
    # Public API — run()
    # =====================================================================

    def run(self) -> None:
        """Start the main event loop."""
        self._root.mainloop()

    # =====================================================================
    # UI Setup
    # =====================================================================

    def _setup_ui(self) -> None:
        """Build all widgets and layout."""

        # ── Top bar ────────────────────────────────────────────────────
        top_bar: ctk.CTkFrame = ctk.CTkFrame(self._root)
        top_bar.pack(fill="x", padx=10, pady=(10, 0))

        self._btn_open: ctk.CTkButton = ctk.CTkButton(
            top_bar,
            text="Open Folder  (Ctrl+O)",
            command=self.load_folder,
            width=200,
        )
        self._btn_open.pack(side="left", padx=5, pady=5)

        self._btn_import_video: ctk.CTkButton = ctk.CTkButton(
            top_bar,
            text="Import Video  (Ctrl+I)",
            command=self.import_video,
            width=200,
            fg_color="#8a4fd1",
            hover_color="#6e3ba8",
        )
        self._btn_import_video.pack(side="left", padx=5, pady=5)

        # ── Main area (image | controls) ───────────────────────────────
        main_frame: ctk.CTkFrame = ctk.CTkFrame(self._root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left — image panel
        self._left_frame: ctk.CTkFrame = ctk.CTkFrame(main_frame, fg_color="gray20")
        self._left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self._image_label: ctk.CTkLabel = ctk.CTkLabel(
            self._left_frame,
            text="No image loaded.\nPress Open Folder or Import Video to begin.",
            font=ctk.CTkFont(size=16),
        )
        self._image_label.pack(fill="both", expand=True, padx=20, pady=20)
        # Resize image when left panel changes size.
        self._left_frame.bind("<Configure>", self._on_resize)

        # Right — controls panel
        self._right_frame: ctk.CTkFrame = ctk.CTkFrame(main_frame, width=360)
        self._right_frame.pack(side="right", fill="y", padx=(5, 0))
        self._right_frame.pack_propagate(False)

        self._build_controls()

        # ── Status bar ─────────────────────────────────────────────────
        self._status_var: tk.StringVar = tk.StringVar(value="Ready — Open a folder or import a video to start.")
        status_bar: ctk.CTkLabel = ctk.CTkLabel(
            self._root,
            textvariable=self._status_var,
            anchor="w",
            font=ctk.CTkFont(size=12),
        )
        status_bar.pack(fill="x", padx=10, pady=(0, 10))

    def _build_controls(self) -> None:
        """Populate the right-hand controls panel."""

        # ── Progress ───────────────────────────────────────────────────
        self._progress_var: tk.StringVar = tk.StringVar(value="Image: 0 / 0")
        ctk.CTkLabel(
            self._right_frame,
            textvariable=self._progress_var,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(15, 0))

        self._filename_var: tk.StringVar = tk.StringVar(value="—")
        ctk.CTkLabel(
            self._right_frame,
            textvariable=self._filename_var,
            font=ctk.CTkFont(size=11),
            text_color="gray70",
            wraplength=320,
        ).pack(pady=(2, 15))

        # ── Separator ──────────────────────────────────────────────────
        ctk.CTkFrame(self._right_frame, height=2, fg_color="gray40").pack(
            fill="x", padx=20, pady=5
        )

        # ── Label groups ───────────────────────────────────────────────
        self._build_radio_group("Eye", EYE_VALUES, self._eye_var)
        self._build_radio_group("Glass", GLASS_VALUES, self._glass_var)
        self._build_radio_group("Face", FACE_VALUES, self._face_var)
        self._build_radio_group("Yawn", YAWN_VALUES, self._yawn_var)
        self._build_radio_group("Seatbelt", SEATBELT_VALUES, self._seatbelt_var)

        # ── Separator ──────────────────────────────────────────────────
        ctk.CTkFrame(self._right_frame, height=2, fg_color="gray40").pack(
            fill="x", padx=20, pady=10
        )

        # ── Preview ────────────────────────────────────────────────────
        ctk.CTkLabel(
            self._right_frame,
            text="Preview:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(pady=(5, 0))

        self._preview_var: tk.StringVar = tk.StringVar(value="")
        self._preview_label: ctk.CTkLabel = ctk.CTkLabel(
            self._right_frame,
            textvariable=self._preview_var,
            font=ctk.CTkFont(size=11),
            text_color="lightblue",
            wraplength=320,
        )
        self._preview_label.pack(pady=(2, 15))

        # ── Buttons ────────────────────────────────────────────────────
        btn_frame: ctk.CTkFrame = ctk.CTkFrame(self._right_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkButton(
            btn_frame,
            text="◀ Previous",
            command=self.previous_image,
            width=140,
        ).grid(row=0, column=0, padx=5, pady=5)

        ctk.CTkButton(
            btn_frame,
            text="Save  (Ctrl+S)",
            command=self.save,
            width=140,
        ).grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkButton(
            btn_frame,
            text="Save & Next  (Enter)",
            command=self.save_and_next,
            width=140,
            fg_color="green",
            hover_color="darkgreen",
        ).grid(row=1, column=0, padx=5, pady=5)

        ctk.CTkButton(
            btn_frame,
            text="Next ▶",
            command=self.next_image,
            width=140,
        ).grid(row=1, column=1, padx=5, pady=5)

    def _build_radio_group(
        self,
        title: str,
        values: tuple[str, str],
        variable: tk.StringVar,
    ) -> None:
        """Create a labelled frame with two radio buttons."""
        group_frame: ctk.CTkFrame = ctk.CTkFrame(self._right_frame)
        group_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(
            group_frame,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=5, pady=(5, 0))

        radio_frame: ctk.CTkFrame = ctk.CTkFrame(group_frame, fg_color="transparent")
        radio_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkRadioButton(
            radio_frame,
            text=LABEL_DISPLAY[values[0]],
            variable=variable,
            value=values[0],
        ).pack(side="left", padx=(0, 20))

        ctk.CTkRadioButton(
            radio_frame,
            text=LABEL_DISPLAY[values[1]],
            variable=variable,
            value=values[1],
        ).pack(side="left")

    # =====================================================================
    # Keyboard bindings
    # =====================================================================

    def _bind_keys(self) -> None:
        """Bind keyboard shortcuts."""
        self._root.bind("<Left>", lambda _: self.previous_image())
        self._root.bind("<Right>", lambda _: self.next_image())
        self._root.bind("<Return>", lambda _: self.save_and_next())
        self._root.bind("<Control-o>", lambda _: self.load_folder())
        self._root.bind("<Control-s>", lambda _: self.save())
        self._root.bind("<Control-i>", lambda _: self.import_video())

        # Digit shortcuts for each label value.
        self._root.bind("1", lambda _: self._eye_var.set(EYE_VALUES[0]))
        self._root.bind("2", lambda _: self._eye_var.set(EYE_VALUES[1]))
        self._root.bind("3", lambda _: self._glass_var.set(GLASS_VALUES[0]))
        self._root.bind("4", lambda _: self._glass_var.set(GLASS_VALUES[1]))
        self._root.bind("5", lambda _: self._face_var.set(FACE_VALUES[0]))
        self._root.bind("6", lambda _: self._face_var.set(FACE_VALUES[1]))
        self._root.bind("7", lambda _: self._yawn_var.set(YAWN_VALUES[0]))
        self._root.bind("8", lambda _: self._yawn_var.set(YAWN_VALUES[1]))
        self._root.bind("9", lambda _: self._seatbelt_var.set(SEATBELT_VALUES[0]))
        self._root.bind("0", lambda _: self._seatbelt_var.set(SEATBELT_VALUES[1]))

    # =====================================================================
    # Event handlers
    # =====================================================================

    def _on_label_changed(self, *_: object) -> None:
        """Called whenever any radio button value changes."""
        self.update_preview()

    def _on_resize(self, event: tk.Event) -> None:
        """Re-fit the current image when the left panel is resized."""
        # Only respond to our own frame's resizes, not children.
        if event.widget == self._left_frame:
            self._refresh_image()

    # =====================================================================
    # Folder operations
    # =====================================================================

    def load_folder(self) -> None:
        """Open a folder dialog and load all supported images."""
        folder_str: str = filedialog.askdirectory(title="Select image folder")
        if not folder_str:
            return

        self._load_folder_path(Path(folder_str))

    def _load_folder_path(self, folder: Path) -> None:
        """Load all supported images from the given folder path."""
        self._folder = folder

        # Collect images sorted by name.
        self._images = sorted(
            [
                p
                for p in folder.iterdir()
                if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS
            ],
            key=lambda p: p.name.lower(),
        )

        if not self._images:
            messagebox.showinfo("No images", "No supported images found in this folder.")
            self._set_status("No images found.")
            self._original_image = None
            self._image_label.configure(image=None, text="No images in folder.")
            self.update_progress()
            return

        self._current_index = 0
        self._load_current_image()
        self._root.title(f"ADAS Label Tool — {folder.name}")
        self._set_status(f"Loaded {len(self._images)} image(s) from {folder.name}.")

    # =====================================================================
    # Video import — extract frames and pre-label them
    # =====================================================================

    def import_video(self) -> None:
        """Pick a video file, extract frames, save them pre-labelled and load them."""
        if cv2 is None:
            messagebox.showerror(
                "Missing dependency",
                "opencv-python is required for video import.\n\n"
                "Install it with:\n    pip install opencv-python",
            )
            return

        video_str: str = filedialog.askopenfilename(
            title="Select video file",
            filetypes=[
                ("Video files", " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))),
                ("All files", "*.*"),
            ],
        )
        if not video_str:
            return
        video_path: Path = Path(video_str)

        # Destination folder for extracted frames.
        out_folder_str: str = filedialog.askdirectory(
            title="Select destination folder for extracted frames"
        )
        if not out_folder_str:
            return
        out_folder: Path = Path(out_folder_str)
        out_folder.mkdir(parents=True, exist_ok=True)

        # Frame interval — ask how many frames to skip between saved frames.
        interval: Optional[int] = simpledialog.askinteger(
            "Frame interval",
            "Save 1 frame every N frames of the video:",
            initialvalue=15,
            minvalue=1,
            maxvalue=100000,
            parent=self._root,
        )
        if interval is None:
            return

        self._set_status(f"Extracting frames from {video_path.name} ...")
        self._root.update_idletasks()

        try:
            saved_paths: list[Path] = self._extract_frames(
                video_path=video_path,
                out_folder=out_folder,
                interval=interval,
            )
        except Exception as exc:
            messagebox.showerror("Video import failed", str(exc))
            self._set_status(f"Video import failed: {exc}")
            return

        if not saved_paths:
            messagebox.showinfo("No frames extracted", "Could not extract any frames from this video.")
            self._set_status("No frames extracted.")
            return

        messagebox.showinfo(
            "Video imported",
            f"Extracted {len(saved_paths)} frame(s) into:\n{out_folder}\n\n"
            "They are already saved with default labels — review and relabel "
            "each frame, then Save.",
        )

        # Load the destination folder into the tool so the user can
        # immediately start reviewing/relabelling the new frames.
        self._load_folder_path(out_folder)

    def _extract_frames(
        self,
        video_path: Path,
        out_folder: Path,
        interval: int,
    ) -> list[Path]:
        """Extract frames from `video_path` every `interval` frames.

        Saved frames follow the naming convention with a default label
        and a sequential 4-digit index (continuing from any existing
        files with the same default-label prefix already in the folder).
        """
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        prefix: str = (
            f"{DEFAULT_EYE}_{DEFAULT_GLASS}_{DEFAULT_FACE}_"
            f"{DEFAULT_YAWN}_{DEFAULT_SEATBELT}_"
        )
        next_index: int = self._find_next_index_in_folder(
            out_folder, DEFAULT_EYE, DEFAULT_GLASS, DEFAULT_FACE,
            DEFAULT_YAWN, DEFAULT_SEATBELT, ".jpg",
        )

        saved_paths: list[Path] = []
        frame_count: int = 0

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                if frame_count % interval == 0:
                    filename: str = self._generate_filename(
                        DEFAULT_EYE, DEFAULT_GLASS, DEFAULT_FACE,
                        DEFAULT_YAWN, DEFAULT_SEATBELT, next_index, ".jpg",
                    )
                    out_path: Path = out_folder / filename

                    # BGR (OpenCV) -> RGB (Pillow) before saving.
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    Image.fromarray(rgb_frame).save(out_path, quality=95)

                    saved_paths.append(out_path)
                    next_index += 1

                frame_count += 1
        finally:
            capture.release()

        return saved_paths

    # =====================================================================
    # Image display
    # =====================================================================

    def _load_current_image(self) -> None:
        """Load the image at _current_index and display it, parsing labels if needed."""
        if not self._images or self._current_index >= len(self._images):
            self._original_image = None
            self._image_label.configure(image=None, text="")
            return

        image_path: Path = self._images[self._current_index]

        # Load with Pillow.
        try:
            self._original_image = Image.open(image_path)
        except Exception as exc:
            self._set_status(f"Error loading image: {exc}")
            self._original_image = None
            self._image_label.configure(image=None, text=f"Error: {exc}")
            self.update_progress()
            return

        # Try to parse labels from the filename.
        self._parse_filename(image_path)

        # Display the image (fit to panel).
        self._refresh_image()
        self.update_progress()
        self.update_preview()

    def _refresh_image(self) -> None:
        """Resize the original image to fit the left panel and display it."""
        if self._original_image is None:
            return

        # Get available space in the left panel (account for padding).
        panel_width: int = self._left_frame.winfo_width() - 40
        panel_height: int = self._left_frame.winfo_height() - 40

        if panel_width <= 0 or panel_height <= 0:
            return

        orig_w, orig_h = self._original_image.size
        scale: float = min(panel_width / orig_w, panel_height / orig_h, 1.0)
        new_w: int = max(1, int(orig_w * scale))
        new_h: int = max(1, int(orig_h * scale))

        resized: Image.Image = self._original_image.resize(
            (new_w, new_h), Image.LANCZOS
        )

        ctk_img: ctk.CTkImage = ctk.CTkImage(
            light_image=resized, size=(new_w, new_h)
        )

        self._image_label.configure(image=ctk_img, text="")

    # =====================================================================
    # Navigation
    # =====================================================================

    def next_image(self) -> None:
        """Move to the next image."""
        if not self._images:
            return
        if self._current_index < len(self._images) - 1:
            self._current_index += 1
            self._load_current_image()
        else:
            self._set_status("Already at the last image.")

    def previous_image(self) -> None:
        """Move to the previous image."""
        if not self._images:
            return
        if self._current_index > 0:
            self._current_index -= 1
            self._load_current_image()
        else:
            self._set_status("Already at the first image.")

    # =====================================================================
    # Save operations
    # =====================================================================

    def save(self) -> None:
        """Rename the current image file with the selected labels."""
        if not self._images:
            self._set_status("No images loaded.")
            return

        success: bool = self._rename_current()
        if success:
            self._load_current_image()

    def save_and_next(self) -> None:
        """Rename the current image, then move to the next one."""
        if not self._images:
            self._set_status("No images loaded.")
            return

        success: bool = self._rename_current()
        if success:
            self.next_image()

    def _rename_current(self) -> bool:
        """Rename the current file.  Return True on success."""
        if self._folder is None or not self._images:
            return False

        current_path: Path = self._images[self._current_index]
        ext: str = current_path.suffix.lower()

        eye: str = self._eye_var.get()
        glass: str = self._glass_var.get()
        face: str = self._face_var.get()
        yawn: str = self._yawn_var.get()
        seatbelt: str = self._seatbelt_var.get()

        index: int = self._find_next_index(eye, glass, face, yawn, seatbelt, ext)
        new_name: str = self._generate_filename(eye, glass, face, yawn, seatbelt, index, ext)
        new_path: Path = self._folder / new_name

        # Avoid renaming to self.
        if current_path.resolve() == new_path.resolve():
            self._set_status(f"Already named: {new_name}")
            return False

        try:
            current_path.rename(new_path)
        except OSError as exc:
            self._set_status(f"Rename failed: {exc}")
            return False

        # Update our image list to point to the new path.
        self._images[self._current_index] = new_path
        self._set_status(f"Saved: {new_name}")
        return True

    # =====================================================================
    # Filename helpers
    # =====================================================================

    @staticmethod
    def _generate_filename(
        eye: str,
        glass: str,
        face: str,
        yawn: str,
        seatbelt: str,
        index: int,
        ext: str,
    ) -> str:
        """Build a filename from label values and a 4-digit index."""
        return f"{eye}_{glass}_{face}_{yawn}_{seatbelt}_{index:04d}{ext}"

    def _find_next_index(
        self,
        eye: str,
        glass: str,
        face: str,
        yawn: str,
        seatbelt: str,
        ext: str,
    ) -> int:
        """Scan the current folder for the next available 4-digit index."""
        if self._folder is None:
            return 1
        return self._find_next_index_in_folder(
            self._folder, eye, glass, face, yawn, seatbelt, ext
        )

    @staticmethod
    def _find_next_index_in_folder(
        folder: Path,
        eye: str,
        glass: str,
        face: str,
        yawn: str,
        seatbelt: str,
        ext: str,
    ) -> int:
        """Scan `folder` for the next available 4-digit index for the given labels."""
        prefix: str = f"{eye}_{glass}_{face}_{yawn}_{seatbelt}_"
        max_idx: int = 0

        if not folder.exists():
            return 1

        for file_path in folder.iterdir():
            if not file_path.is_file():
                continue
            name: str = file_path.name
            if not name.startswith(prefix):
                continue
            if file_path.suffix.lower() != ext:
                continue
            # Extract the numeric part between prefix and extension.
            rest: str = file_path.stem[len(prefix):]
            if rest.isdigit() and len(rest) == 4:
                max_idx = max(max_idx, int(rest))

        return max_idx + 1

    def _parse_filename(self, path: Path) -> None:
        """Extract labels from a filename matching the naming convention."""
        name: str = path.name
        match = FILENAME_PATTERN.match(name)
        if match is None:
            return

        # Set radio buttons without triggering trace callbacks (which
        # would update preview unnecessarily — we update it afterwards).
        self._eye_var.set(match.group(1).lower())
        self._glass_var.set(match.group(2).lower())
        self._face_var.set(match.group(3).lower())
        self._yawn_var.set(match.group(4).lower())
        self._seatbelt_var.set(match.group(5).lower())

    # =====================================================================
    # Preview
    # =====================================================================

    def update_preview(self) -> None:
        """Update the preview filename label based on current radio button values."""
        if not self._images:
            self._preview_var.set("")
            return

        current_path: Path = self._images[self._current_index]
        ext: str = current_path.suffix.lower()

        eye: str = self._eye_var.get()
        glass: str = self._glass_var.get()
        face: str = self._face_var.get()
        yawn: str = self._yawn_var.get()
        seatbelt: str = self._seatbelt_var.get()

        index: int = self._find_next_index(eye, glass, face, yawn, seatbelt, ext)
        preview: str = self._generate_filename(eye, glass, face, yawn, seatbelt, index, ext)
        self._preview_var.set(preview)

    # =====================================================================
    # Status & progress
    # =====================================================================

    def update_progress(self) -> None:
        """Update the progress counter and current filename display."""
        if not self._images:
            self._progress_var.set("Image: 0 / 0")
            self._filename_var.set("—")
            return

        total: int = len(self._images)
        current: int = self._current_index + 1  # 1-based display
        self._progress_var.set(f"Image: {current} / {total}")

        fname: str = self._images[self._current_index].name
        # Truncate for display if too long.
        if len(fname) > 50:
            fname = fname[:47] + "..."
        self._filename_var.set(fname)

    def _set_status(self, message: str) -> None:
        """Set the status bar text."""
        self._status_var.set(message)


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    app: LabelTool = LabelTool()
    app.run()