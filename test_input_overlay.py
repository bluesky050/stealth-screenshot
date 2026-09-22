import unittest
from unittest.mock import Mock, patch

from stealth_screenshot.input_overlay import DragSelection, InputOverlay, screen_point


class SelectionTests(unittest.TestCase):
    def test_negative_origin(self):
        self.assertEqual(screen_point((100 << 16) | 200, (-2560, -221)), (-2360, -121))
        self.assertEqual(screen_point((0xFFFE << 16) | 0xFFFF, (0, 0)), (-1, -2))

    def test_duplicate_down_keeps_first_point(self):
        selection = DragSelection()
        selection.arm()
        self.assertTrue(selection.down((-100, 20)))
        self.assertFalse(selection.down((200, 100)))
        self.assertEqual(selection.finish((30, 80)), ((-100, 20), (30, 80)))
        self.assertFalse(selection.armed)

    def test_cancel_drops_pending_selection(self):
        selection = DragSelection()
        selection.arm()
        selection.down((10, 10))
        selection.cancel()
        self.assertIsNone(selection.finish((200, 200)))

    def test_hide_precedes_callback(self):
        events = []
        overlay = InputOverlay(lambda x, y: events.append('start'), lambda x, y: events.append('end'))
        overlay.selection.arm()
        overlay.selection.down((10, 10))
        with patch.object(overlay, '_hide', side_effect=lambda: events.append('hide')):
            overlay._finish((100, 100))
        self.assertEqual(events, ['hide', 'start', 'end'])

    def test_hide_even_when_callback_raises(self):
        overlay = InputOverlay(Mock(), Mock(side_effect=RuntimeError('test')))
        overlay.selection.arm()
        overlay.selection.down((10, 10))
        with patch.object(overlay, '_hide') as hide:
            with self.assertLogs('stealth_screenshot.input_overlay', level='ERROR'):
                overlay._finish((100, 100))
        hide.assert_called_once()
        self.assertFalse(overlay.is_armed())

    def test_hidden_native_window_start_stop(self):
        import win32gui
        overlay = InputOverlay(Mock(), Mock())
        overlay.start()
        hwnd, thread = overlay.hwnd, overlay._thread
        try:
            self.assertTrue(win32gui.IsWindow(hwnd))
            self.assertFalse(win32gui.IsWindowVisible(hwnd))
        finally:
            overlay.stop()
        self.assertFalse(thread.is_alive())
        self.assertFalse(win32gui.IsWindow(hwnd))


if __name__ == '__main__':
    unittest.main()
