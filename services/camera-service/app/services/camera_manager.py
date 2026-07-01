"""Thread-safe webcam manager with background capture and JPEG pre-encoding."""

import threading
import time
from typing import Optional

import cv2
import numpy as np

from app.core.config import get_settings
from app.utils.logger import get_logger


class CameraManager:
    """Manages a single webcam capture session in a background thread.

    Continuously reads frames, stores the latest frame and its JPEG encoding
    in memory, and serves them via thread-safe accessors.

    Only one CameraManager instance per process is intended.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._camera_index: int = settings.CAMERA_INDEX
        self._jpeg_quality: int = settings.JPEG_QUALITY
        self._target_width: int = settings.FRAME_WIDTH
        self._target_height: int = settings.FRAME_HEIGHT

        self._capture: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()
        self._stop_event: threading.Event = threading.Event()

        self._latest_frame: Optional[np.ndarray] = None
        self._latest_jpeg: Optional[bytes] = None
        self._frame_id: int = 0
        self._timestamp: float = 0.0
        self._width: int = 0
        self._height: int = 0
        self._fps: float = 0.0
        self._total_frames: int = 0
        self._start_time: float = 0.0

        self._logger = get_logger()

    # ------------------------------------------------------------------
    # Public properties — thread-safe reads
    # ------------------------------------------------------------------

    @property
    def latest_frame(self) -> Optional[np.ndarray]:
        """Return a copy of the most recent frame (BGR numpy array)."""
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    @property
    def latest_jpeg(self) -> Optional[bytes]:
        """Return the pre-encoded JPEG bytes of the latest frame."""
        with self._lock:
            return self._latest_jpeg

    @property
    def frame_id(self) -> int:
        """Return the current sequential frame id."""
        with self._lock:
            return self._frame_id

    @property
    def timestamp(self) -> float:
        """Return the Unix timestamp of the latest frame capture."""
        with self._lock:
            return self._timestamp

    @property
    def width(self) -> int:
        """Return the actual capture width in pixels."""
        with self._lock:
            return self._width

    @property
    def height(self) -> int:
        """Return the actual capture height in pixels."""
        with self._lock:
            return self._height

    @property
    def fps(self) -> float:
        """Return the instantaneous FPS of the capture loop."""
        with self._lock:
            return self._fps

    @property
    def is_running(self) -> bool:
        """Return True if the background capture thread is active."""
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open the webcam and launch the background capture thread.

        If the camera is unavailable at startup the thread still starts and
        will attempt reconnection automatically.  The service remains healthy
        (though degraded) and serves whatever frames become available later.
        """
        if self.is_running:
            self._logger.warning("CameraManager is already running")
            return

        self._logger.info("Opening camera index=%d", self._camera_index)
        self._try_open_camera()

        self._stop_event.clear()
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="camera-capture")
        self._thread.start()
        self._logger.info("Camera capture thread started")

    def _try_open_camera(self) -> None:
        """Attempt to open the camera.  Logs on failure; never raises."""
        try:
            self._capture = cv2.VideoCapture(self._camera_index)
            if self._capture is None or not self._capture.isOpened():
                self._logger.warning(
                    "Camera index=%d not available — will retry in background",
                    self._camera_index,
                )
                self._capture = None
                return

            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._target_width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._target_height)

            actual_width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._width = actual_width if actual_width > 0 else self._target_width
            self._height = actual_height if actual_height > 0 else self._target_height
            self._logger.info("Camera opened (%dx%d)", self._width, self._height)
        except Exception:
            self._logger.exception("Exception opening camera index=%d", self._camera_index)
            self._capture = None

    def stop(self) -> None:
        """Signal the background thread to exit and release the webcam."""
        if not self.is_running:
            return
        self._logger.info("Stopping camera capture")
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._logger.info("Camera capture stopped. Total frames: %d", self._total_frames)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return runtime statistics as a dictionary."""
        uptime = time.time() - self._start_time if self._start_time > 0 else 0.0
        with self._lock:
            total = self._total_frames
            cam_fps = self._fps
        return {
            "uptime": round(uptime, 2),
            "total_frames": total,
            "camera_fps": round(cam_fps, 2),
        }

    # ------------------------------------------------------------------
    # Background capture loop
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        """Main loop running in the background thread.

        Continuously reads frames from the webcam, encodes them to JPEG,
        and stores the result in thread-safe properties.
        Handles webcam disconnection with reconnection attempts.
        """
        frame_count: int = 0
        fps_window: list[float] = []
        fps_update_interval: float = 1.0
        last_fps_update: float = time.time()
        reconnect_delay: float = 1.0

        while not self._stop_event.is_set():
            if self._capture is None or not self._capture.isOpened():
                self._logger.warning("Camera disconnected. Attempting reconnect...")
                time.sleep(reconnect_delay)
                if self._capture is not None:
                    self._capture.release()
                self._capture = cv2.VideoCapture(self._camera_index)
                if self._capture is None or not self._capture.isOpened():
                    self._logger.error("Reconnect failed. Retrying in %.1fs", reconnect_delay)
                    continue
                self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._target_width)
                self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._target_height)
                self._logger.info("Camera reconnected")

            success, frame = self._capture.read()
            if not success or frame is None:
                self._logger.warning("Empty frame read from camera")
                continue

            now = time.time()
            frame_count += 1

            encode_success, jpeg_buffer = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]
            )
            if not encode_success:
                self._logger.warning("JPEG encode failed for frame %d", frame_count)
                continue

            with self._lock:
                self._latest_frame = frame
                self._latest_jpeg = jpeg_buffer.tobytes()
                self._frame_id = frame_count
                self._timestamp = now
                self._total_frames = frame_count

            fps_window.append(now)
            fps_window = [t for t in fps_window if t > now - 5.0]

            if now - last_fps_update >= fps_update_interval:
                if len(fps_window) >= 2:
                    avg_fps = len(fps_window) / (fps_window[-1] - fps_window[0]) if fps_window[-1] != fps_window[0] else 0.0
                else:
                    avg_fps = 0.0
                with self._lock:
                    self._fps = avg_fps
                last_fps_update = now

        self._logger.info("Capture loop exiting")
