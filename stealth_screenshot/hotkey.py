"""Global hotkey listener using a direct WH_KEYBOARD_LL hook.

Replaces the third-party ``keyboard`` library with a native Win32
low-level keyboard hook — the same mechanism already used for the
mouse hook.  This avoids a known issue where ``keyboard``'s internal
listener thread fails to fire callbacks in PyInstaller ``--noconsole``
(windowed) builds.
"""

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_MENU = 0x12  # Alt
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_SHIFT = 0x10
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1

from .win32_hooks import user32, kernel32, HOOKPROC


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


# Hook callback type: (int nCode, WPARAM wParam, LPARAM lParam) -> LRESULT


# ---------------------------------------------------------------------------
# Key-name → virtual-key-code mapping
# ---------------------------------------------------------------------------

_KEY_MAP = {
    "ctrl": VK_CONTROL,
    "control": VK_CONTROL,
    "alt": VK_MENU,
    "menu": VK_MENU,
    "shift": VK_SHIFT,
    "q": 0x51,
    "w": 0x57,
    "e": 0x45,
    "r": 0x52,
    "a": 0x41,
    "s": 0x53,
    "d": 0x44,
    "f": 0x46,
    "z": 0x5A,
    "x": 0x58,
    "c": 0x43,
    "v": 0x56,
    "p": 0x50,
    "print": 0x2A,   # VK_SNAPSHOT
    "printscreen": 0x2A,
}


def _parse_hotkey(hotkey_str: str) -> list[int]:
    """Parse a hotkey string like 'ctrl+q' into a list of VK codes."""
    parts = hotkey_str.lower().replace(" ", "").split("+")
    codes = []
    for part in parts:
        if part in _KEY_MAP:
            codes.append(_KEY_MAP[part])
        elif len(part) == 1 and part.isalpha():
            codes.append(ord(part.upper()))
        else:
            raise ValueError(f"Unknown key: {part!r} in hotkey {hotkey_str!r}")
    return codes


class HotkeyListener:
    """Registers a global hotkey via WH_KEYBOARD_LL.

    The last key in the combination is the *trigger* key; all preceding
    keys are *modifiers* that must be held down when the trigger is
    pressed.
    """

    def __init__(self, hotkey: str, callback: Callable[[], None],
                 quit_hotkey: str | None = None,
                 quit_callback: Callable[[], None] | None = None):
        self._callback = callback
        self._quit_callback = quit_callback
        self._codes = _parse_hotkey(hotkey)
        self._trigger_vk = self._codes[-1]
        self._modifier_vks = set(self._codes[:-1])
        self._quit_trigger_vk: Optional[int] = None
        self._quit_modifier_vks: set[int] = set()
        if quit_hotkey and quit_callback:
            qcodes = _parse_hotkey(quit_hotkey)
            self._quit_trigger_vk = qcodes[-1]
            self._quit_modifier_vks = set(qcodes[:-1])

        self._pressed: set[int] = set()
        self._hook_handle = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._ready = threading.Event()
        self._startup_error = None
        self._thread_id = None
        self._fired = False  # debounce — one fire per key-down streak

    def start(self) -> None:
        """Install the keyboard hook and start the message-pump thread."""
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
        """Uninstall the hook and stop the thread."""
        self._running.clear()
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _hook_loop(self) -> None:
        """Thread target: install hook and run message pump."""
        hook_self = self
        self._thread_id = kernel32.GetCurrentThreadId()
        startup_msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(startup_msg), None, 0, 0, 0)

        @HOOKPROC
        def _low_level_handler(nCode, wParam, lParam):
            if nCode == HC_ACTION:
                info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = info.vkCode

                # Track modifier state; also treat L/R variants as the generic modifier
                is_keydown = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                is_keyup = wParam in (WM_KEYUP, WM_SYSKEYUP)

                # Normalise L/R modifier keys to their generic VK
                if vk in (VK_LCONTROL, VK_RCONTROL):
                    vk_norm = VK_CONTROL
                elif vk in (VK_LMENU, VK_RMENU):
                    vk_norm = VK_MENU
                elif vk in (VK_LSHIFT, VK_RSHIFT):
                    vk_norm = VK_SHIFT
                else:
                    vk_norm = vk

                if is_keydown:
                    hook_self._pressed.add(vk_norm)
                elif is_keyup:
                    hook_self._pressed.discard(vk_norm)
                    if vk_norm == hook_self._trigger_vk:
                        hook_self._fired = False
                    if hook_self._quit_trigger_vk and vk_norm == hook_self._quit_trigger_vk:
                        hook_self._fired = False

                # Check trigger
                if is_keydown and vk_norm == hook_self._trigger_vk and not hook_self._fired:
                    if hook_self._modifier_vks.issubset(hook_self._pressed):
                        hook_self._fired = True
                        try:
                            hook_self._callback()
                        except Exception:
                            pass

                # Check quit trigger
                if (is_keydown and hook_self._quit_trigger_vk
                        and vk_norm == hook_self._quit_trigger_vk
                        and not hook_self._fired):
                    if hook_self._quit_modifier_vks.issubset(hook_self._pressed):
                        hook_self._fired = True
                        try:
                            hook_self._quit_callback()
                        except Exception:
                            pass

            return user32.CallNextHookEx(hook_self._hook_handle, nCode, wParam, lParam)

        self._hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, _low_level_handler, kernel32.GetModuleHandleW(None), 0
        )
        if not self._hook_handle:
            self._startup_error = ctypes.WinError(ctypes.get_last_error())
            self._running.clear()
            self._ready.set()
            return
        self._ready.set()

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
