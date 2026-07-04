"""Live display module for Camera-Service.

Runs a separate thread that renders the camera feed with AI result
overlays in an OpenCV window. Independent of the capture and messaging
threads so display FPS never blocks capture or inference.
"""

import threading
import time
from typing import Optional

import cv2
import numpy as np

from app.models.messages import DriverResultMessage, SeatbeltResultMessage
from app.services.camera_manager import CameraManager
from app.utils.logger import get_logger

logger = get_logger()

DISPLAY_FPS = 30

GREEN = (0, 255, 0)
RED = (0, 0, 255)
BLUE = (255, 0, 0)
YELLOW = (0, 255, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


class DisplayOverlay:
    """Manages the OpenCV display window with HUD overlay.

    Runs in its own thread, fetching the latest frame from CameraManager
    and the latest AI results from the result consumer.
    """

    def __init__(self, camera_manager: CameraManager) -> None:
        self._camera_manager = camera_manager
        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()

        self._driver_result: Optional[DriverResultMessage] = None
        self._seatbelt_result: Optional[SeatbeltResultMessage] = None
        self._result_lock: threading.Lock = threading.Lock()

        self._display_fps: float = 0.0
        self._fps_frame_count: int = 0
        self._fps_last_time: float = 0.0

    def update_driver_result(self, result: DriverResultMessage) -> None:
        with self._result_lock:
            self._driver_result = result

    def update_seatbelt_result(self, result: SeatbeltResultMessage) -> None:
        with self._result_lock:
            self._seatbelt_result = result

    def start(self) -> None:
        """Launch the display thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._display_loop, daemon=True, name="display")
        self._thread.start()
        logger.info("Display thread started")

    def stop(self) -> None:
        """Signal the display thread to stop."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        cv2.destroyAllWindows()
        logger.info("Display stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _display_loop(self) -> None:
        """Main display loop rendering frames with HUD overlay."""
        cv2.namedWindow("ADAS Monitor", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("ADAS Monitor", 960, 640)

        self._fps_last_time = time.time()

        while not self._stop_event.is_set():
            loop_start = time.time()

            frame = self._camera_manager.latest_frame
            if frame is None:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                self._put_text_bg(frame, "Waiting for camera...", (200, 240),
                                  font_scale=1.0, color=YELLOW)

            frame = self._draw_hud(frame)

            cv2.imshow("ADAS Monitor", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                logger.info("Display closed by user")
                self._stop_event.set()
                break

            self._fps_frame_count += 1
            fps_now = time.time()
            if fps_now - self._fps_last_time >= 1.0:
                self._display_fps = self._fps_frame_count / (fps_now - self._fps_last_time)
                self._fps_frame_count = 0
                self._fps_last_time = fps_now

            elapsed = time.time() - loop_start
            target_delay = 1.0 / DISPLAY_FPS
            if elapsed < target_delay:
                time.sleep(target_delay - elapsed)

        cv2.destroyAllWindows()

    def _draw_hud(self, frame: np.ndarray) -> np.ndarray:
        """Draw heads-up display with AI results."""
        h, w = frame.shape[:2]

        with self._result_lock:
            driver = self._driver_result
            seatbelt = self._seatbelt_result

        sleepy_text = f"Sleepy : {'YES' if (driver and driver.sleepy) else 'NO'}"
        seatbelt_text = f"Seatbelt : {'YES' if (seatbelt and seatbelt.seatbelt) else 'NO'}"
        fps_text = f"FPS : {self._display_fps:.1f}"

        self._put_text_bg(frame, sleepy_text, (10, 30), font_scale=0.6, color=WHITE)
        self._put_text_bg(frame, seatbelt_text, (10, 60), font_scale=0.6, color=WHITE)
        self._put_text_bg(frame, fps_text, (10, 90), font_scale=0.6, color=WHITE)

        return frame

    @staticmethod
    def _put_text_bg(
        img: np.ndarray,
        text: str,
        pos: tuple,
        font_scale: float = 0.55,
        thickness: int = 2,
        color: tuple = WHITE,
        bg: tuple = BLACK,
    ) -> None:
        (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        x, y = pos
        cv2.rectangle(img, (x, y - th - 4), (x + tw + 6, y + baseline), bg, -1)
        cv2.putText(img, text, (x + 3, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
