"""Core screenshot orchestration — hotkey, input window, capture, clipboard."""

import logging
import threading
import time

from .clipboard import ClipboardWriter
from .input_overlay import InputOverlay
from .screen_capture import ScreenCapture

logger = logging.getLogger(__name__)

MIN_DRAG_DISTANCE = 5  # px — ignore micro-clicks


class ScreenshotController:
    """Coordinates the invisible screenshot flow.

    Flow:
      1. Hotkey pressed → show selection window
      2. Mouse down → record start point
      3. Mouse up → record end point, compute rect, capture, clipboard
      4. Disarm
    """

    def __init__(self):
        self._selector = InputOverlay(
            on_drag_start=self._on_drag_start,
            on_drag_end=self._on_drag_end,
        )
        self._start_point: tuple[int, int] | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the hidden selection window thread."""
        self._selector.start()

    def trigger(self) -> None:
        """Called when the hotkey is pressed — enters screenshot mode."""
        if self._selector.is_armed():
            return
        with self._lock:
            self._start_point = None
        self._selector.arm()
        logger.info("hotkey_trigger screenshot_armed")

    def _on_drag_start(self, x: int, y: int) -> None:
        self._start_point = (x, y)
        logger.info("mouse_down x=%d y=%d", x, y)

    def _on_drag_end(self, x: int, y: int) -> None:
        logger.info("mouse_up x=%d y=%d", x, y)
        with self._lock:
            start = self._start_point
            self._start_point = None

        if start is None:
            logger.warning("mouse_up_without_start")
            return

        sx, sy = start
        ex, ey = x, y

        # Compute rect — normalise to positive width/height
        rx = min(sx, ex)
        ry = min(sy, ey)
        rw = abs(ex - sx)
        rh = abs(ey - sy)

        if rw < MIN_DRAG_DISTANCE or rh < MIN_DRAG_DISTANCE:
            logger.info("Drag too small (%d×%d), ignoring", rw, rh)
            return

        logger.info("capture_begin rect=(%d,%d,%d,%d)", rx, ry, rw, rh)
        started = time.monotonic()
        try:
            img = ScreenCapture.capture((rx, ry, rw, rh))
        except Exception:
            logger.exception("capture_exception")
            return
        if img is None:
            logger.warning("Screen capture failed — clipboard untouched")
            return

        logger.info("capture_returned width=%d height=%d elapsed_ms=%.1f", img.width, img.height, (time.monotonic() - started) * 1000)
        logger.info("clipboard_begin")
        try:
            result = ClipboardWriter.write_image(img)
            logger.info("clipboard_writer_returned result=%s total_elapsed_ms=%.1f", result, (time.monotonic() - started) * 1000)
        except Exception:
            logger.exception("clipboard_exception")

    def stop(self) -> None:
        """Stop the selection window thread."""
        self._selector.stop()
