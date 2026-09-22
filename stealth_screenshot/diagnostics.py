"""Metadata-only diagnostics. Disk writes run outside input hooks."""
import atexit
import ctypes
import logging
import logging.handlers
from pathlib import Path
import queue
import sys
from ctypes import wintypes


def configure():
    if '--diagnose' not in sys.argv:
        return False
    folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    output = logging.FileHandler(folder / 'screenshot-diagnostic.log', encoding='utf-8')
    output.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s'))
    messages = queue.SimpleQueue()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(logging.handlers.QueueHandler(messages))
    listener = logging.handlers.QueueListener(messages, output)
    listener.start()
    atexit.register(listener.stop)
    logging.info('diagnostic_start version=vmware-overlay-1 pid=%s', __import__('os').getpid())
    return True


def sample(controller):
    hook = controller._selector
    if not hook.is_armed():
        return
    u = ctypes.WinDLL('user32', use_last_error=True)
    u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    u.GetCursorPos.restype = wintypes.BOOL
    point = wintypes.POINT()
    cursor_ok = u.GetCursorPos(ctypes.byref(point))
    logging.info('input_sample armed=%s dragging=%s selection_thread_alive=%s events=%s last_event=%s cursor_ok=%s cursor=(%s,%s)',
                 hook.is_armed(), hook.selection.start is not None, bool(hook._thread and hook._thread.is_alive()),
                 hook._diagnostic_events, hook._diagnostic_last_event, bool(cursor_ok), point.x, point.y)
