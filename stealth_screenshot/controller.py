"""Core screenshot orchestration — ties hotkey, mouse hook, capture, clipboard."""

import logging
import threading

from .clipboard import ClipboardWriter
from .mouse_hook import MouseHook
from .screen_capture import ScreenCapture

logger = logging.getLogger(__name__)

MIN_DRAG_DISTANCE = 5  # px — ignore micro-clicks


class ScreenshotController:
    """Coordinates the invisible screenshot flow.

    Flow:
      1. Hotkey pressed → arm mouse hook
      2. Mouse down → record start point
      3. Mouse up → record end point, compute rect, capture, clipboard
      4. Disarm
    """

    def __init__(self):
        self._mouse_hook = MouseHook(
            on_drag_start=self._on_drag_start,
            on_drag_end=self._on_drag_end,
        )
        self._start_point: tuple[int, int] | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the mouse hook thread (call once at app startup)."""
        self._mouse_hook.start()

    def trigger(self) -> None:
        """Called when the hotkey is pressed — enters screenshot mode."""
        with self._lock:
            self._start_point = None
        self._mouse_hook.arm()
        logger.debug("Screenshot mode armed")

    def _on_drag_start(self, x: int, y: int) -> None:
        self._start_point = (x, y)
        logger.debug("Drag start at (%d, %d)", x, y)

    def _on_drag_end(self, x: int, y: int) -> None:
        with self._lock:
            start = self._start_point
            self._start_point = None

        if start is None:
            return

        sx, sy = start
        ex, ey = x, y

        # Compute rect — normalise to positive width/height
        rx = min(sx, ex)
        ry = min(sy, ey)
        rw = abs(ex - sx)
        rh = abs(ey - sy)

        if rw < MIN_DRAG_DISTANCE or rh < MIN_DRAG_DISTANCE:
            logger.debug("Drag too small (%d×%d), ignoring", rw, rh)
            return

        logger.debug("Capturing rect (%d, %d, %d, %d)", rx, ry, rw, rh)
        img = ScreenCapture.capture((rx, ry, rw, rh))
        if img is None:
            logger.warning("Screen capture failed — clipboard untouched")
            return

        if ClipboardWriter.write_image(img):
            logger.debug("Screenshot copied to clipboard (%dx%d)", img.width, img.height)
        else:
            logger.warning("Failed to write to clipboard")

    def stop(self) -> None:
        """Stop the mouse hook thread."""
        self._mouse_hook.stop()
