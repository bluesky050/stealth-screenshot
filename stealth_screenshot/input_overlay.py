"""Nearly transparent Win32 window that owns selection input."""
import ctypes
from ctypes import wintypes
import logging
import threading
import win32api
import win32con as wc
import win32gui as gui

logger = logging.getLogger(__name__)
WM_ARM = wc.WM_APP + 1
WM_STOP = wc.WM_APP + 2
TIMER_ID = 1
TIMEOUT_MS = 30000
OVERLAY_ALPHA = 1
u = ctypes.WinDLL('user32', use_last_error=True)
u.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
u.SetTimer.restype = ctypes.c_size_t
u.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
u.KillTimer.restype = wintypes.BOOL
u.SetThreadDpiAwarenessContext.argtypes = [wintypes.HANDLE]
u.SetThreadDpiAwarenessContext.restype = wintypes.HANDLE
u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
u.AttachThreadInput.restype = wintypes.BOOL
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.GetWindowThreadProcessId.restype = wintypes.DWORD
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
dwm = ctypes.WinDLL('dwmapi')
dwm.DwmFlush.argtypes = []
dwm.DwmFlush.restype = ctypes.c_long


def screen_point(lparam, origin):
    """Decode signed client coordinates, preserving negative screen origins."""
    x = ctypes.c_short(lparam & 0xffff).value
    y = ctypes.c_short((lparam >> 16) & 0xffff).value
    return origin[0] + x, origin[1] + y


class DragSelection:
    def __init__(self):
        self.armed = False
        self.start = None

    def arm(self):
        self.armed = True
        self.start = None

    def down(self, point):
        if not self.armed or self.start is not None:
            return False
        self.start = point
        return True

    def finish(self, point):
        result = (self.start, point) if self.armed and self.start is not None else None
        self.cancel()
        return result

    def cancel(self):
        self.armed = False
        self.start = None


class InputOverlay:
    def __init__(self, on_drag_start, on_drag_end):
        self._on_drag_start = on_drag_start
        self._on_drag_end = on_drag_end
        self.selection = DragSelection()
        self.hwnd = None
        self._thread = None
        self._ready = threading.Event()
        self._startup_error = None
        self._origin = (0, 0)
        self._previous_foreground = None
        self._diagnostic_events = 0
        self._diagnostic_last_event = None

    def is_armed(self):
        return self.selection.armed

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._startup_error = None
        self._thread = threading.Thread(target=self._run, name='selection-window', daemon=True)
        self._thread.start()
        if not self._ready.wait(5):
            raise RuntimeError('Selection window startup timed out')
        if self._startup_error:
            raise self._startup_error

    def arm(self):
        if not self.hwnd:
            raise RuntimeError('Selection window is not running')
        gui.PostMessage(self.hwnd, WM_ARM, 0, 0)

    def stop(self):
        if self.hwnd:
            gui.PostMessage(self.hwnd, WM_STOP, 0, 0)
        if self._thread:
            self._thread.join(5)
            if self._thread.is_alive():
                raise RuntimeError('Selection window did not stop')

    def _run(self):
        name = 'StealthSelection_' + str(id(self))
        registered = False
        instance = win32api.GetModuleHandle(None)
        try:
            if not u.SetThreadDpiAwarenessContext(wintypes.HANDLE(-4)):
                raise ctypes.WinError(ctypes.get_last_error())
            window_class = gui.WNDCLASS()
            window_class.hInstance = instance
            window_class.lpszClassName = name
            window_class.lpfnWndProc = self._wndproc
            window_class.hCursor = gui.LoadCursor(None, wc.IDC_ARROW)
            window_class.hbrBackground = gui.GetStockObject(wc.BLACK_BRUSH)
            gui.RegisterClass(window_class)
            registered = True
            self.hwnd = gui.CreateWindowEx(
                wc.WS_EX_LAYERED | wc.WS_EX_TOPMOST | wc.WS_EX_TOOLWINDOW,
                name, 'Screenshot selection', wc.WS_POPUP,
                0, 0, 1, 1, 0, 0, instance, None)
            # Alpha zero (or WS_EX_TRANSPARENT) would pass clicks to VMware.
            gui.SetLayeredWindowAttributes(self.hwnd, 0, OVERLAY_ALPHA, wc.LWA_ALPHA)
            logger.info('overlay_ready alpha=%d', OVERLAY_ALPHA)
            self._ready.set()
            gui.PumpMessages()
        except Exception as error:
            self._startup_error = error
            logger.exception('overlay_thread_failed')
        finally:
            self.selection.cancel()
            if self.hwnd and gui.IsWindow(self.hwnd):
                gui.DestroyWindow(self.hwnd)
            self.hwnd = None
            if registered:
                gui.UnregisterClass(name, instance)
            self._ready.set()

    def _activate_foreground(self, target, reference):
        try:
            gui.SetForegroundWindow(target)
        except Exception:
            reference_thread = u.GetWindowThreadProcessId(reference, None) if reference else 0
            own_thread = kernel32.GetCurrentThreadId()
            if not reference_thread or reference_thread == own_thread:
                raise
            if not u.AttachThreadInput(own_thread, reference_thread, True):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                gui.SetForegroundWindow(target)
            finally:
                u.AttachThreadInput(own_thread, reference_thread, False)

    def _show(self):
        if self.selection.armed:
            return
        self._origin = (win32api.GetSystemMetrics(76), win32api.GetSystemMetrics(77))
        width, height = win32api.GetSystemMetrics(78), win32api.GetSystemMetrics(79)
        if width <= 0 or height <= 0:
            raise RuntimeError('Invalid virtual desktop dimensions')
        self._previous_foreground = gui.GetForegroundWindow()
        self.selection.arm()
        gui.SetWindowPos(self.hwnd, wc.HWND_TOPMOST, *self._origin, width, height, wc.SWP_SHOWWINDOW)
        gui.ShowWindow(self.hwnd, wc.SW_SHOW)
        self._activate_foreground(self.hwnd, self._previous_foreground)
        gui.SetFocus(self.hwnd)
        if gui.GetForegroundWindow() != self.hwnd:
            raise RuntimeError('Selection window could not obtain foreground input')
        gui.SetCapture(self.hwnd)
        if gui.GetCapture() != self.hwnd:
            raise RuntimeError('Selection window could not capture mouse')
        if not u.SetTimer(self.hwnd, TIMER_ID, TIMEOUT_MS, None):
            raise ctypes.WinError(ctypes.get_last_error())
        logger.info('overlay_armed origin=%s size=(%d,%d)', self._origin, width, height)

    def _hide(self):
        # State first: ReleaseCapture synchronously sends WM_CAPTURECHANGED.
        self.selection.cancel()
        u.KillTimer(self.hwnd, TIMER_ID)
        restore = gui.GetForegroundWindow() == self.hwnd
        gui.ShowWindow(self.hwnd, wc.SW_HIDE)
        if gui.GetCapture() == self.hwnd:
            gui.ReleaseCapture()
        if restore and self._previous_foreground and gui.IsWindow(self._previous_foreground):
            try:
                self._activate_foreground(self._previous_foreground, self._previous_foreground)
            except Exception:
                logger.exception('foreground_restore_failed')
        hr = dwm.DwmFlush()
        if hr < 0:
            logger.warning('dwm_flush_failed hresult=%s', hr)
        logger.info('overlay_hidden')

    def _cancel(self, reason):
        if self.selection.armed:
            self._hide()
            logger.info('overlay_cancel reason=%s', reason)

    def _finish(self, point):
        points = self.selection.finish(point)
        self._hide()
        if points:
            try:
                self._on_drag_start(*points[0])
                self._on_drag_end(*points[1])
            except Exception:
                logger.exception('selection_callback_failed')

    def _wndproc(self, hwnd, message, wparam, lparam):
        try:
            if message == WM_ARM:
                self._show()
                return 0
            if message == WM_STOP or message == wc.WM_CLOSE:
                self._cancel('stop')
                gui.DestroyWindow(hwnd)
                return 0
            if message == wc.WM_DESTROY:
                gui.PostQuitMessage(0)
                return 0
            if self.selection.armed:
                if message in (wc.WM_MOUSEMOVE, wc.WM_LBUTTONDOWN, wc.WM_LBUTTONUP):
                    self._diagnostic_events += 1
                    self._diagnostic_last_event = message
                    point = screen_point(lparam, self._origin)
                    if message == wc.WM_LBUTTONDOWN:
                        accepted = self.selection.down(point)
                        logger.info('overlay_mouse_down point=%s accepted=%s', point, accepted)
                    elif message == wc.WM_LBUTTONUP:
                        logger.info('overlay_mouse_up point=%s', point)
                        self._finish(point)
                    return 0
                if message == wc.WM_KEYDOWN and wparam == wc.VK_ESCAPE:
                    self._cancel('escape')
                    return 0
                if message in (wc.WM_RBUTTONDOWN, wc.WM_TIMER, wc.WM_CANCELMODE, wc.WM_DISPLAYCHANGE, 0x02E0):
                    self._cancel('message_' + str(message))
                    return 0
                if message == wc.WM_CAPTURECHANGED and lparam != hwnd:
                    self._cancel('capture_lost')
                    return 0
                if message == wc.WM_ACTIVATE and (wparam & 0xffff) == wc.WA_INACTIVE:
                    self._cancel('focus_lost')
                    return 0
            return gui.DefWindowProc(hwnd, message, wparam, lparam)
        except Exception:
            logger.exception('overlay_message_failed message=%s', message)
            self._cancel('error')
            return 0

