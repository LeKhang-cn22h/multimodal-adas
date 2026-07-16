# TS-label-tool: Labeling Tool Implementation

## Thuộc Feature
`.opencode/knowledge/features/FEAT-label-tool.md`

## Kiến trúc

```
scripts/label_tool.py   # 1 file duy nhất
```

### Cấu trúc class

```
class LabelTool:
    # State
    _folder: Path | None
    _images: list[Path]
    _current_index: int
    _labels: dict[str, tk.StringVar]   # eye, glass, face, yawn, seatbelt

    # Core methods
    load_folder()       # Mở folder dialog, load danh sách ảnh
    show_image()        # Load + resize ảnh hiện tại, fit cửa sổ
    update_preview()    # Cập nhật preview filename từ labels hiện tại
    parse_filename()    # Parse tên file → labels (nếu match pattern)
    generate_filename() # Tạo tên mới từ labels + index
    find_next_index()   # Tìm số XXXX tiếp theo chưa tồn tại
    rename_current()    # Rename file hiện tại → tên mới
    next_image()        # Chuyển ảnh kế
    previous_image()    # Chuyển ảnh trước
    save()              # Rename + refresh
    save_and_next()     # Rename + next
    update_status()     # Cập nhật status bar
    update_progress()   # Cập nhật text tiến độ + tên file
    setup_ui()          # Build toàn bộ giao diện
    bind_keys()         # Bind phím tắt
```

### Layout

```
┌──────────────────────────────────────────────────┐
│  [Open Folder]                                   │
├────────────────────┬─────────────────────────────┤
│                    │  Image: 15 / 250            │
│                    │  IMG_0012.jpg               │
│     IMAGE          │                             │
│     (fit,          │  ── Eye ──                  │
│     no stretch)    │  ○ eyeopen  ○ eyeclose      │
│                    │                             │
│                    │  ── Glass ──                │
│                    │  ○ glass    ○ noglass       │
│                    │                             │
│                    │  ── Face ──                 │
│                    │  ○ face     ○ noface        │
│                    │                             │
│                    │  ── Yawn ──                 │
│                    │  ○ yawn     ○ noyawn        │
│                    │                             │
│                    │  ── Seatbelt ──             │
│                    │  ○ seatbelt ○ noseatbelt    │
│                    │                             │
│                    │  Preview:                    │
│                    │  eyeopen_glass_face...       │
│                    │                             │
│                    │  [Previous] [Save]           │
│                    │  [Save & Next] [Next]        │
├────────────────────┴─────────────────────────────┤
│  Status: Ready                                   │
└──────────────────────────────────────────────────┘
```

## Logic + AI
Không — tool thuần GUI.

## API Contract
Không có API — standalone desktop app.

### Naming convention pattern
```
{eye}_{glass}_{face}_{yawn}_{seatbelt}_{XXXX}.{ext}

eye ∈ {eyeopen, eyeclose}
glass ∈ {glass, noglass}
face ∈ {face, noface}
yawn ∈ {yawn, noyawn}
seatbelt ∈ {seatbelt, noseatbelt}
XXXX: zero-padded 4-digit integer
ext: jpg|jpeg|png|bmp|webp (giữ nguyên từ file gốc)
```

## Rủi ro & câu hỏi mở
- Không.

## Ảnh hưởng tới service khác
Không.

## Trạng thái xác nhận
`[x] Đã xác nhận bởi người dùng ngày 2026-07-15 — ĐÃ IMPLEMENT`
