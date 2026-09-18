"""Stealth Screenshot — invisible screen capture for Windows.

No windows, no overlays, no visual feedback. Hotkey triggers mouse
drag-select; the captured region goes straight to the clipboard.
"""

import ctypes
import logging
import os
import sys
import threading
import time
from ctypes import wintypes

from .config import load_config
from .controller import ScreenshotController
from .hotkey import HotkeyListener

# ---------------------------------------------------------------------------
# DPI awareness — must be set before any GUI / screen operations
# ---------------------------------------------------------------------------

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

user32 = ctypes.windll.user32
user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL


def _set_dpi_awareness() -> None:
    """Tell Windows we want physical pixels, not scaled virtual pixels."""
    try:
        user32.SetProcessDpiAwarenessContext(
            wintypes.HANDLE(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        )
    except Exception:
        # Fallback: SetProcessDPIAware (Win 8.1+)
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Optional system-tray icon
# ---------------------------------------------------------------------------

def _create_tray_icon() -> "PilImage.Image":
    """Draw a small camera icon for the system tray (16x16, white on dark)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Camera body
    d.rounded_rectangle([1, 4, 14, 13], radius=2, fill=(40, 40, 40, 255))
    # Camera top bump (viewfinder)
    d.rectangle([5, 2, 9, 4], fill=(40, 40, 40, 255))
    # Lens
    d.ellipse([5, 6, 11, 12], fill=(80, 160, 255, 255))
    d.ellipse([7, 8, 9, 10], fill=(200, 230, 255, 255))
    return img


def _run_tray(on_quit: threading.Event, hotkey_str: str) -> None:
    """Start a system-tray icon with Exit menu item. Always shown."""
    try:
        import pystray
        from PIL import Image as PilImage
    except ImportError:
        return

    def _on_exit(icon, item):
        on_quit.set()
        icon.stop()

    icon_img = _create_tray_icon()
    menu = pystray.Menu(
        pystray.MenuItem(f"截图热键: {hotkey_str}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", _on_exit),
    )
    tray = pystray.Icon(
        "stealth-screenshot",
        icon_img,
        "Stealth Screenshot (运行中)",
        menu,
    )
    tray.run()


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("STEALTH_DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger("stealth-screenshot")

    # 1. DPI awareness
    _set_dpi_awareness()
    logger.info("DPI awareness set to per-monitor-v2")

    # 2. Load config
    cfg = load_config()
    hotkey_str = cfg.get("hotkey", "ctrl+alt+q")
    quit_hotkey_str = cfg.get("quit_hotkey")
    tray_enabled = cfg.get("tray_icon", False)

    # 3. Create controller and start mouse hook thread
    controller = ScreenshotController()
    controller.start()

    quit_event = threading.Event()

    # 4. Hotkey listener
    def _trigger():
        controller.trigger()

    def _quit():
        logger.info("Quit hotkey pressed")
        quit_event.set()

    listener = HotkeyListener(
        hotkey=hotkey_str,
        callback=_trigger,
        quit_hotkey=quit_hotkey_str,
        quit_callback=_quit,
    )
    listener.start()
    logger.info("Hotkey registered: %s", hotkey_str)

    # 5. Tray icon (always on — shows in system tray, not taskbar)
    threading.Thread(target=_run_tray, args=(quit_event, hotkey_str), daemon=True).start()
    logger.info("Tray icon enabled")

    # 6. Keep the process alive
    logger.info("Stealth Screenshot running. Press %s to capture.", hotkey_str)
    if quit_hotkey_str:
        logger.info("Press %s to quit.", quit_hotkey_str)

    try:
        while not quit_event.is_set():
            quit_event.wait(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        controller.stop()
        logger.info("Stealth Screenshot stopped.")


if __name__ == "__main__":
    main()
