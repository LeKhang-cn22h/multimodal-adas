from __future__ import annotations

from pathlib import Path
from tkinter import Tk, filedialog


def pick_video() -> str | None:
    root = Tk()
    root.withdraw()

    filename = filedialog.askopenfilename(
        title="Chọn video",
        filetypes=[
            ("Video", "*.mp4 *.avi *.mov *.mkv"),
            ("All files", "*.*"),
        ],
    )

    root.destroy()

    if filename == "":
        return None

    return str(Path(filename))