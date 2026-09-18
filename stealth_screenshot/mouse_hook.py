"""Low-level mouse hook for invisible drag-to-select.

Uses WH_MOUSE_LL to intercept mouse events globally without creating
any on-screen window, overlay, or visual feedback.
"""

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Optional

# Win32 constants
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
HC_ACTION = 0

from .win32_hooks import user32, kernel32, HOOKPROC


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


# Hook callback type: (int nCode, WPARAM wParam, LPARAM lParam) -> LRESULT


class MouseHook:
    """Installs a low-level mouse hook to capture drag-to-select events.

    No window is created. The hook runs inside a dedicated thread that
    maintains its own message pump, keeping the main thread free.
    """

    def __init__(self, on_drag_start: Callable[[int, int], None],
                 on_drag_end: Callable[[int, int], None]):
        self._on_drag_start = on_drag_start
        self._on_drag_end = on_drag_end
        self._hook_handle = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._ready = threading.Event()
        self._startup_error = None
        self._thread_id = None
        self._armed = threading.Event()  # set when in screenshot mode
        self._dragging = False

    def arm(self) -> None:
        """Enter screenshot mode — start listening for mouse drag."""
        self._dragging = False
        self._armed.set()

    def disarm(self) -> None:
        """Exit screenshot mode."""
        self._armed.clear()
        self._dragging = False

    def is_armed(self) -> bool:
        return self._armed.is_set()

    def start(self) -> None:
        """Start the hook thread."""
        if self._running.is_set():
            return
        self._running.set()
        self._ready.clear()
        self._startup_error = None
        self._thread = threading.Thread(target=self._hook_loop, daemon=True)
        self._thread.start()
        if not self._ready.wait(5):
            self.stop()
            raise RuntimeError("Hook startup timed out")
        if self._startup_error is not None:
            self.stop()
            raise self._startup_error

    def stop(self) -> None:
        """Stop the hook thread and uninstall the hook."""
        self._running.clear()
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _hook_loop(self) -> None:
        """Thread target: install hook and run message pump."""
        # Capture references for the callback closure
        hook_self = self
        self._thread_id = kernel32.GetCurrentThreadId()
        startup_msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(startup_msg), None, 0, 0, 0)

        @HOOKPROC
        def _low_level_handler(nCode, wParam, lParam):
            if nCode == HC_ACTION and hook_self._armed.is_set():
                if wParam == WM_LBUTTONDOWN:
                    info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    hook_self._dragging = True
                    hook_self._on_drag_start(info.pt.x, info.pt.y)
                    # Consume the press so the foreground app cannot start a selection.
                    return 1
                elif wParam == WM_LBUTTONUP and hook_self._dragging:
                    info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    hook_self._dragging = False
                    hook_self._disarm_and_callback(info.pt.x, info.pt.y)
                    # Match the consumed press; do not deliver an orphan release.
                    return 1
            return user32.CallNextHookEx(hook_self._hook_handle, nCode, wParam, lParam)

        self._hook_handle = user32.SetWindowsHookExW(
            WH_MOUSE_LL, _low_level_handler, kernel32.GetModuleHandleW(None), 0
        )
        if not self._hook_handle:
            self._startup_error = ctypes.WinError(ctypes.get_last_error())
            self._running.clear()
            self._ready.set()
            return
        self._ready.set()

        # Message pump
        msg = wintypes.MSG()
        while self._running.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook_handle:
            user32.UnhookWindowsHookEx(self._hook_handle)
            self._hook_handle = None

    def _disarm_and_callback(self, x: int, y: int) -> None:
        """Disarm (exit screenshot mode) and deliver the end coordinate."""
        self._armed.clear()
        self._on_drag_end(x, y)
