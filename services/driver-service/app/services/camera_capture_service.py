"""Camera capture service — background thread that reads webcam frames.

TS-service-merge / ADR-006:
    Opens cv2.VideoCapture in a daemon thread, encodes frames as JPEG,
    pushes them into a shared queue.Queue for the AI worker thread.
"""

from __future__ import annotations

import queue
import threading
import time
import socket
import os

import cv2
import numpy as np

from app.utils.logger import get_logger

logger = get_logger()


class CameraCaptureService:
    """Captures webcam frames in a background thread."""

    def __init__(
        self,
        frame_queue: queue.Queue,
        camera_index: int | str = 1,
        width: int = 640,
        height: int = 480,
        jpeg_quality: int = 85,
    ) -> None:
        self._queue = frame_queue
        self._camera_index = camera_index
        self._width = width
        self._height = height
        self._jpeg_quality = jpeg_quality

        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._latest_jpeg: bytes | None = None
        self._lock = threading.Lock()

        self._frame_count = 0
        self._dropped_count = 0
        self._fps = 0.0
        self._fps_t0 = 0.0
        self._fps_counter = 0

        self._current_source: int | str = camera_index

        # UDP socket for dashboard streaming
        self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._dashboard_host = os.getenv("DASHBOARD_UDP_HOST", "127.0.0.1")
        self._dashboard_port = int(os.getenv("DASHBOARD_UDP_PORT", 1235))

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def dropped_frames(self) -> int:
        return self._dropped_count

    def start(self, source: int | str | None = None) -> None:
        if self.is_running:
            self.stop()

        if source is not None:
            self._current_source = source
        else:
            self._current_source = self._camera_index

        if isinstance(self._current_source, str) and self._current_source.isdigit():
            self._current_source = int(self._current_source)

        logger.info("Opening video source: %s", self._current_source)
        self._cap = cv2.VideoCapture(self._current_source)
        
        if isinstance(self._current_source, int):
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)

        self._fps_t0 = time.time()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="camera-capture",
        )
        self._thread.start()
        logger.info("Camera capture started")

    def stop(self) -> None:
        logger.info("Stopping camera capture...")
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("Camera capture stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._cap is None:
                break
            ret, frame = self._cap.read()
            if not ret:
                if not isinstance(self._current_source, int):
                    # Loop video if it is a file
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(0.01)
                continue

            # Encode JPEG
            _, jpeg = cv2.imencode(
                ".jpg", frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            jpeg_bytes = jpeg.tobytes()

            # Stream via UDP to Dashboard if frame size is small enough
            try:
                if len(jpeg_bytes) < 65000:
                    self._udp_sock.sendto(jpeg_bytes, (self._dashboard_host, self._dashboard_port))
            except Exception:
                pass

            # Store latest
            with self._lock:
                self._latest_jpeg = jpeg_bytes

            # Push to worker queue (drop if full)
            try:
                self._queue.put_nowait(jpeg_bytes)
                self._frame_count += 1
                self._fps_counter += 1
            except queue.Full:
                self._dropped_count += 1

            # FPS counter (update every second)
            now = time.time()
            elapsed = now - self._fps_t0
            if elapsed >= 1.0:
                self._fps = self._fps_counter / elapsed
                self._fps_counter = 0
                self._fps_t0 = now
