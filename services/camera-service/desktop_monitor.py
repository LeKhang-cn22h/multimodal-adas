"""Desktop monitoring dashboard for ADAS camera + seatbelt detection.

Displays live camera feed with seatbelt detection overlays in an OpenCV window.
Fetches frames from camera-service and detection results from seatbelt-service.

Usage:
    python desktop_monitor.py [--camera CAMERA_URL] [--seatbelt SEATBELT_URL]

Controls:
    q / ESC       - quit
    p             - pause / resume
    s             - toggle seatbelt overlay
"""

import argparse
import os
import sys
import time
from typing import Optional

import cv2
import httpx
import numpy as np

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CAMERA_URL = "http://localhost:8005"
DEFAULT_SEATBELT_URL = "http://localhost:8007"
DISPLAY_FPS = 30
DETECTION_INTERVAL = 3.0

# ---------------------------------------------------------------------------
# Colors (BGR)
# ---------------------------------------------------------------------------
GREEN = (0, 255, 0)
RED = (0, 0, 255)
BLUE = (255, 0, 0)
YELLOW = (0, 255, 255)
ORANGE = (0, 165, 255)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

CLASS_COLORS = {
    "cell phone": ORANGE,
    "drinking": (0, 165, 255),
    "eyeglass": YELLOW,
    "hands off": RED,
    "hands on": CYAN,
    "mask": (255, 0, 255),
    "seatbelt": GREEN,
}


def put_text_bg(
    img: np.ndarray,
    text: str,
    pos: tuple[int, int],
    font_scale: float = 0.55,
    thickness: int = 2,
    color: tuple[int, int, int] = WHITE,
    bg: tuple[int, int, int] = BLACK,
) -> None:
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    x, y = pos
    cv2.rectangle(img, (x, y - th - 4), (x + tw + 6, y + baseline), bg, -1)
    cv2.putText(img, text, (x + 3, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)


def draw_detections(frame: np.ndarray, detections: list[dict]) -> np.ndarray:
    """Draw bounding boxes and labels for each detection."""
    for det in detections:
        bbox = det.get("bbox", [])
        if len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        label = det.get("class_name", "?")
        conf = det.get("confidence", 0.0)
        color = CLASS_COLORS.get(label, WHITE)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        put_text_bg(frame, f"{label} {conf:.2f}", (x1, y1 - 5), color=color)
    return frame


def draw_hud(
    frame: np.ndarray,
    seatbelt_ok: bool,
    warning: bool,
    streak: int,
    display_fps: float,
    detection_count: int,
    show_overlay: bool,
) -> np.ndarray:
    """Draw heads-up display with status info."""
    h, w = frame.shape[:2]

    if not show_overlay:
        put_text_bg(frame, "Overlay OFF", (10, 30), font_scale=0.6, color=(180, 180, 180))
        return frame

    if seatbelt_ok:
        status = "SEATBELT: OK"
        bg_color = (0, 100, 0)
    elif warning:
        status = f"WARNING: NO SEATBELT ({streak}f)"
        bg_color = (0, 0, 180)
    else:
        status = f"Checking... ({streak}f)"
        bg_color = (100, 80, 0)

    (tw, th), _ = cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    cv2.rectangle(frame, (10, 8), (20 + tw, 18 + th + 6), bg_color, -1)
    cv2.putText(frame, status, (15, 14 + th + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 2)

    info_lines = [
        f"FPS: {display_fps:.1f}",
        f"Detections: {detection_count}",
    ]
    for i, line in enumerate(info_lines):
        put_text_bg(frame, line, (10, 60 + i * 24), font_scale=0.5, color=(200, 200, 200))

    return frame


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="ADAS Desktop Monitoring Dashboard")
    parser.add_argument("--camera", default=DEFAULT_CAMERA_URL, help="Camera service URL")
    parser.add_argument("--seatbelt", default=DEFAULT_SEATBELT_URL, help="Seatbelt service URL")
    parser.add_argument("--detection-interval", type=float, default=DETECTION_INTERVAL,
                        help="Seconds between detection calls")
    parser.add_argument("--no-overlay", action="store_true", help="Start with overlay disabled")
    args = parser.parse_args()

    camera_frame_url = args.camera.rstrip("/") + "/frame"
    seatbelt_check_url = args.seatbelt.rstrip("/") + "/check"

    print(f"Camera  : {camera_frame_url}")
    print(f"Seatbelt: {seatbelt_check_url}")
    print("Controls: q/ESC=quit  p=pause  s=toggle overlay")
    print("=" * 50)

    cv2.namedWindow("ADAS Monitor", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ADAS Monitor", 960, 640)

    latest_detections: list[dict] = []
    seatbelt_ok: bool = False
    warning: bool = False
    streak: int = 0
    detection_count: int = 0
    last_detection_time: float = 0.0
    paused: bool = False
    show_overlay: bool = not args.no_overlay

    fps_frame_count: int = 0
    fps_last_time: float = time.time()
    display_fps: float = 0.0

    frame: Optional[np.ndarray] = None

    print("[INFO] Starting monitor loop...")

    try:
        while True:
            loop_start = time.time()

            if not paused:
                frame = fetch_frame(camera_frame_url)
                if frame is None:
                    if frame is None:
                        blank = np.zeros((480, 640, 3), dtype=np.uint8)
                        put_text_bg(blank, "Waiting for camera...", (200, 240),
                                    font_scale=1.0, color=YELLOW)
                        frame = blank

                now = time.time()
                if show_overlay and (now - last_detection_time >= args.detection_interval):
                    result = fetch_detection(seatbelt_check_url)
                    if result:
                        latest_detections = result.get("detections", [])
                        seatbelt_ok = result.get("seatbelt_detected", False)
                        warning = result.get("warning", False)
                        streak = result.get("no_seatbelt_streak", 0)
                        detection_count = len(latest_detections)
                    last_detection_time = now

                if show_overlay and latest_detections:
                    frame = draw_detections(frame, latest_detections)
                frame = draw_hud(frame, seatbelt_ok, warning, streak, display_fps,
                                 detection_count, show_overlay)

                fps_frame_count += 1
                fps_now = time.time()
                if fps_now - fps_last_time >= 1.0:
                    display_fps = fps_frame_count / (fps_now - fps_last_time)
                    fps_frame_count = 0
                    fps_last_time = fps_now

            cv2.imshow("ADAS Monitor", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("[INFO] Quit by user")
                break
            elif key == ord("p"):
                paused = not paused
                print("[INFO]", "Paused" if paused else "Resumed")
            elif key == ord("s"):
                show_overlay = not show_overlay
                print("[INFO]", "Overlay OFF" if not show_overlay else "Overlay ON")

            elapsed = time.time() - loop_start
            target_delay = 1.0 / DISPLAY_FPS
            if elapsed < target_delay:
                time.sleep(target_delay - elapsed)

    except KeyboardInterrupt:
        print("[INFO] Interrupted")
    finally:
        cv2.destroyAllWindows()
        print("[DONE] Monitor closed")


def fetch_frame(url: str) -> Optional[np.ndarray]:
    """Fetch JPEG frame from camera-service and decode to BGR numpy array."""
    try:
        resp = httpx.get(url, timeout=2.0)
        if resp.status_code == 200 and resp.content:
            np_arr = np.frombuffer(resp.content, dtype=np.uint8)
            return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except httpx.RequestError:
        pass
    return None


def fetch_detection(url: str) -> Optional[dict]:
    """Fetch detection results from seatbelt-service."""
    try:
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
    except httpx.RequestError:
        pass
    return None


if __name__ == "__main__":
    main()
