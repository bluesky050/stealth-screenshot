import threading
import time
import unittest
import win32con as wc
import win32gui as gui
from stealth_screenshot.input_overlay import InputOverlay


def lparam(x, y):
    return ((y & 0xffff) << 16) | (x & 0xffff)


class NativeMessageTests(unittest.TestCase):
    def test_window_hides_before_selection_callback(self):
        received = []
        completed = threading.Event()
        overlay = None
        def on_start(x, y):
            received.append(('start', x, y, bool(gui.IsWindowVisible(overlay.hwnd))))
        def on_end(x, y):
            received.append(('end', x, y, bool(gui.IsWindowVisible(overlay.hwnd))))
            completed.set()
        overlay = InputOverlay(on_start, on_end)
        overlay.start()
        try:
            overlay.arm()
            gui.PostMessage(overlay.hwnd, wc.WM_LBUTTONDOWN, wc.MK_LBUTTON, lparam(30, 40))
            gui.PostMessage(overlay.hwnd, wc.WM_LBUTTONDOWN, wc.MK_LBUTTON, lparam(50, 60))
            gui.PostMessage(overlay.hwnd, wc.WM_LBUTTONUP, 0, lparam(130, 140))
            self.assertTrue(completed.wait(3))
            self.assertEqual([row[0] for row in received], ['start', 'end'])
            self.assertFalse(received[0][3])
            self.assertFalse(received[1][3])
            self.assertGreater(received[1][1] - received[0][1], 50)
            self.assertGreater(received[1][2] - received[0][2], 50)
            self.assertFalse(overlay.is_armed())
        finally:
            overlay.stop()

    def test_escape_cancels_without_callback(self):
        received = []
        overlay = InputOverlay(lambda x, y: received.append((x, y)), lambda x, y: received.append((x, y)))
        overlay.start()
        try:
            overlay.arm()
            gui.PostMessage(overlay.hwnd, wc.WM_LBUTTONDOWN, wc.MK_LBUTTON, lparam(30, 40))
            gui.PostMessage(overlay.hwnd, wc.WM_KEYDOWN, wc.VK_ESCAPE, 0)
            gui.PostMessage(overlay.hwnd, wc.WM_LBUTTONUP, 0, lparam(130, 140))
            deadline = time.monotonic() + 3
            while overlay.is_armed() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(overlay.is_armed())
            self.assertFalse(gui.IsWindowVisible(overlay.hwnd))
            self.assertEqual(received, [])
        finally:
            overlay.stop()
