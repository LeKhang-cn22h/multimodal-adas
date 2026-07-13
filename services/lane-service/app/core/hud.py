"""
hud.py — ADAS HUD Renderer
===========================
Vẽ giao diện HUD trực quan lên frame OpenCV BGR.

Layout:
┌──────────────────────────────────────────────┐
│  LANE MONITOR              ◄ CENTER ►         │  ← header + direction badge
│  ┌────────────────────────────────────────┐   │
│  │  L ◄──────────────●──────────────► R  │   │  ← offset gauge bar
│  └────────────────────────────────────────┘   │
│              +0.074m                          │  ← offset value
│  ╔══════════════════════════════════════╗     │
│  ║  ✓  SYSTEM SAFE                     ║     │  ← alert badge
│  ╚══════════════════════════════════════╝     │
└──────────────────────────────────────────────┘
"""

import cv2
import numpy as np
from typing import Optional


# ── Màu sắc ────────────────────────────────────────────────────────────────
CLR_SAFE    = (40,  180,  40)   # Xanh lá
CLR_WARNING = (20,  190, 200)   # Vàng cam (BGR)
CLR_DANGER  = (30,   30, 220)   # Đỏ
CLR_BG      = (22,   26,  35)   # Nền panel tối
CLR_BORDER  = (70,   80,  95)   # Viền nhẹ
CLR_TEXT    = (210, 215, 220)   # Text chính
CLR_MUTED   = (110, 118, 130)   # Text mờ
CLR_CENTER  = (50,  200, 100)   # Xanh lá sáng (CENTER)
CLR_OFFSIDE = (60,   80, 240)   # Đỏ cam (LEFT/RIGHT)


def _alert_palette(alert: str):
    if alert == "DANGER":
        return CLR_DANGER,  "DANGER",  "! VEHICLE TOO CLOSE"
    if alert == "WARNING":
        return CLR_WARNING, "WARNING", "~ KEEP SAFE DISTANCE"
    return CLR_SAFE,        "SAFE",    "✓  SYSTEM SAFE"


def _direction_palette(direction: str):
    if direction in ("LEFT", "RIGHT"):
        return CLR_OFFSIDE, direction
    return CLR_CENTER, "CENTER"


def draw_hud(
    frame: np.ndarray,
    lane_offset: Optional[float],
    direction: str,
    distance_alert: str,
    lane_detected: bool = True,
    *,
    x: int = 12,
    y: int = 12,
    width: int = 360,
) -> None:
    """
    Vẽ HUD ADAS lên frame BGR (in-place).

    Args:
        frame:          Frame BGR từ OpenCV.
        lane_offset:    Offset so với tâm làn (m). None nếu chưa phát hiện.
        direction:      "LEFT" | "CENTER" | "RIGHT" | "UNKNOWN".
        distance_alert: "SAFE" | "WARNING" | "DANGER".
        lane_detected:  Có phát hiện làn không.
        x, y:           Góc trên-trái của panel.
        width:          Chiều rộng panel.
    """
    h_frame, w_frame = frame.shape[:2]
    panel_h = 148
    pad = 14

    # ── 1. Nền panel semi-transparent ──────────────────────────────────────
    x2, y2 = min(x + width, w_frame - 4), min(y + panel_h, h_frame - 4)
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x2, y2), CLR_BG, -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    # Viền panel mỏng
    cv2.rectangle(frame, (x, y), (x2, y2), CLR_BORDER, 1, cv2.LINE_AA)

    # ── 2. Header: "LANE MONITOR" + direction badge ─────────────────────────
    dir_color, dir_text = _direction_palette(direction)

    cv2.putText(frame, "LANE MONITOR",
                (x + pad, y + 22),
                cv2.FONT_HERSHEY_DUPLEX, 0.52, CLR_TEXT, 1, cv2.LINE_AA)

    # Direction badge (pill shape)
    badge_label = f"< {dir_text} >" if direction == "CENTER" else \
                  (f"<< {dir_text}" if direction == "LEFT" else f"{dir_text} >>")
    (bw, bh), _ = cv2.getTextSize(badge_label, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
    bx = x2 - bw - pad - 8
    by = y + 8
    cv2.rectangle(frame, (bx - 6, by), (bx + bw + 6, by + bh + 6), dir_color, -1)
    cv2.rectangle(frame, (bx - 6, by), (bx + bw + 6, by + bh + 6), CLR_BORDER, 1)
    cv2.putText(frame, badge_label,
                (bx, by + bh + 1),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

    # Đường kẻ ngang phân cách header
    cv2.line(frame, (x + pad, y + 32), (x2 - pad, y + 32), CLR_BORDER, 1)

    # ── 3. Offset Gauge Bar ─────────────────────────────────────────────────
    bar_x  = x + pad
    bar_y  = y + 45
    bar_w  = width - pad * 2
    bar_h  = 16
    bar_x2 = bar_x + bar_w
    bar_y2 = bar_y + bar_h

    # Nền bar (tối)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x2, bar_y2), (40, 44, 55), -1)

    # Vùng "safe zone" màu xanh ở giữa (±20% bar width)
    safe_half = int(bar_w * 0.15)
    mid_x = bar_x + bar_w // 2
    cv2.rectangle(frame,
                  (mid_x - safe_half, bar_y + 2),
                  (mid_x + safe_half, bar_y2 - 2),
                  (0, 60, 0), -1)

    # Vạch center
    cv2.line(frame, (mid_x, bar_y - 2), (mid_x, bar_y2 + 2), (80, 200, 80), 1)

    # Indicator — vị trí xe
    max_offset = 0.75          # ±0.75m → full bar
    off_val = lane_offset if (lane_detected and lane_offset is not None) else 0.0
    off_clamped = max(-max_offset, min(max_offset, off_val))
    # offset dương = lệch phải trong camera space
    ind_x = int(mid_x - off_clamped / max_offset * (bar_w // 2))
    ind_x = max(bar_x + 6, min(bar_x2 - 6, ind_x))

    ind_color = dir_color if lane_detected else CLR_MUTED

    # Vẽ indicator hình thoi (diamond)
    diamond = np.array([
        [ind_x,     bar_y - 3],
        [ind_x - 7, bar_y + bar_h // 2],
        [ind_x,     bar_y2 + 3],
        [ind_x + 7, bar_y + bar_h // 2],
    ], np.int32)
    cv2.fillPoly(frame, [diamond], ind_color)
    cv2.polylines(frame, [diamond], True, (200, 200, 200), 1, cv2.LINE_AA)

    # Viền bar
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x2, bar_y2), CLR_BORDER, 1)

    # Nhãn L / R + mũi tên
    cv2.putText(frame, "L",  (bar_x - 1, bar_y2 + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, CLR_MUTED, 1, cv2.LINE_AA)
    cv2.putText(frame, "R",  (bar_x2 - 8, bar_y2 + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, CLR_MUTED, 1, cv2.LINE_AA)

    # ── 4. Offset value text ────────────────────────────────────────────────
    if lane_detected and lane_offset is not None:
        off_str = f"{lane_offset:+.3f} m"
    else:
        off_str = "-- m"

    (ow, _), _ = cv2.getTextSize(off_str, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
    cv2.putText(frame, off_str,
                (mid_x - ow // 2, bar_y2 + 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, ind_color, 1, cv2.LINE_AA)

    # ── 5. Alert Badge ──────────────────────────────────────────────────────
    alert_color, _, alert_text = _alert_palette(distance_alert)

    ab_y1 = y + 105
    ab_y2 = y + 130
    ab_x1 = x + pad
    ab_x2 = x2 - pad

    # Nền badge
    cv2.rectangle(frame, (ab_x1, ab_y1), (ab_x2, ab_y2), alert_color, -1)
    # Viền sáng hơn
    lighter = tuple(min(255, c + 60) for c in alert_color)
    cv2.rectangle(frame, (ab_x1, ab_y1), (ab_x2, ab_y2), lighter, 1, cv2.LINE_AA)

    (atw, ath), _ = cv2.getTextSize(alert_text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
    at_x = ab_x1 + (ab_x2 - ab_x1 - atw) // 2
    at_y = ab_y1 + (ab_y2 - ab_y1 + ath) // 2
    cv2.putText(frame, alert_text, (at_x, at_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)

    # ── 6. "NO LANE" overlay khi không phát hiện ──────────────────────────
    if not lane_detected:
        nl_y = y + 140
        cv2.putText(frame, "NO LANE DETECTED",
                    (x + pad, nl_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (80, 80, 200), 1, cv2.LINE_AA)
