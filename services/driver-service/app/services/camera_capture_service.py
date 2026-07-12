"""CameraCaptureService — background webcam capture thread.

Manages cv2.VideoCapture in a daemon thread, encodes frames to JPEG,
and pushes them into a queue.Queue for the AI worker thread.

Thread-safety:
    - cv2.VideoCapture is owned exclusively by the capture thread.
    - latest_jpeg, fps, frame_id, dropped_frames are read/written
      under a threading.Lock (main thread reads for GET /frame/stats).
    - queue.Queue is thread-safe by design (capture puts, worker gets).

Backlog protection (TS-service-merge):
    - queue.Queue(maxsize=MAX_QUEUE_SIZE, default 2)
    - put_nowait() — if queue is full, frame is dropped immediately
      and dropped_frames counter is incremented.
    - Worker thread does NO drop logic — maxsize handles it.
"""

import queue
import threading
import time
from typing import Optional

import cv2

from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger()


class CameraCaptureService:
    """Manages webcam capture in a background thread.

    Thread-safe: capture thread writes latest_jpeg + fps under lock;
    main thread reads for GET /frame and GET /stats.

    Pushes JPEG frames to queue.Queue for the worker thread to process.
    """

    def __init__(self, frame_queue: queue.Queue) -> None:
        settings = get_settings()

        self._camera_index: int = settings.CAMERA_INDEX
        self._jpeg_quality: int = settings.JPEG_QUALITY
        self._frame_width: int = settings.FRAME_WIDTH
        self._frame_height: int = settings.FRAME_HEIGHT
        self._max_queue_size: int = settings.MAX_QUEUE_SIZE

        self._capture: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frame_queue = frame_queue

        # ── Thread-safe state (read under lock) ────────────────────
        self._latest_jpeg: Optional[bytes] = None
        self._fps: float = 0.0
        self._frame_id: int = 0
        self._is_running: bool = False
        self._dropped_frames: int = 0

    # ------------------------------------------------------------------
    # Public API (main thread)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open webcam and launch the capture thread."""
        self._try_open_camera()

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="camera-capture",
        )
        self._thread.start()
        with self._lock:
            self._is_running = True
        logger.info(
            "Camera capture started (index=%d, %dx%d, jpeg_quality=%d)",
            self._camera_index, self._frame_width,
            self._frame_height, self._jpeg_quality,
        )

    def stop(self) -> None:
        """Signal the capture thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._release_camera()
        with self._lock:
            self._is_running = False
        logger.info("Camera capture stopped")

    # ── Thread-safe properties ──────────────────────────────────────

    @property
    def latest_jpeg(self) -> Optional[bytes]:
        """Latest JPEG bytes (thread-safe)."""
        with self._lock:
            return self._latest_jpeg

    @property
    def fps(self) -> float:
        """Current capture FPS (thread-safe)."""
        with self._lock:
            return self._fps

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    @property
    def dropped_frames(self) -> int:
        with self._lock:
            return self._dropped_frames

    # ------------------------------------------------------------------
    # Internal — camera management
    # ------------------------------------------------------------------

    def _try_open_camera(self) -> None:
        """Open cv2.VideoCapture and set resolution."""
        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera index {self._camera_index}"
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._frame_height)
        self._capture = cap
        logger.info(
            "Camera opened: index=%d, actual resolution=%dx%d",
            self._camera_index,
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def _release_camera(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None

    # ------------------------------------------------------------------
    # Internal — capture loop (runs in background thread)
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        """Main capture loop: read → encode → push to queue.

        Runs in daemon thread "camera-capture".  Auto-reconnects
        if the camera disconnects.
        """
        fps_frame_count = 0
        fps_start_time = time.time()

        while not self._stop_event.is_set():
            # ── Auto-reconnect on disconnect ──────────────────────
            if self._capture is None or not self._capture.isOpened():
                logger.warning("Camera disconnected, reconnecting...")
                self._release_camera()
                try:
                    self._try_open_camera()
                except Exception as exc:
                    logger.error("Camera reconnect failed: %s", exc)
                    if self._stop_event.wait(timeout=1.0):
                        break
                    continue

            ret, frame = self._capture.read()
            if not ret or frame is None:
                logger.warning("Camera read returned empty frame")
                if self._stop_event.wait(timeout=0.1):
                    break
                continue

            # ── Encode JPEG ────────────────────────────────────────
            success, jpeg_arr = cv2.imencode(
                ".jpg", frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            if not success:
                continue
            jpeg_bytes = jpeg_arr.tobytes()

            # ── Update thread-safe state ───────────────────────────
            with self._lock:
                self._latest_jpeg = jpeg_bytes
                self._frame_id += 1
                frame_id_snapshot = self._frame_id

            # ── Push to AI worker queue (non-blocking) ─────────────
            try:
                self._frame_queue.put_nowait(jpeg_bytes)
            except queue.Full:
                with self._lock:
                    self._dropped_frames += 1

            # ── FPS calculation (5-second sliding window) ──────────
            fps_frame_count += 1
            elapsed = time.time() - fps_start_time
            if elapsed >= 5.0:
                fps_val = fps_frame_count / elapsed
                with self._lock:
                    self._fps = round(fps_val, 2)
                fps_frame_count = 0
                fps_start_time = time.time()
