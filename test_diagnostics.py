import unittest
from unittest.mock import patch
from stealth_screenshot.controller import ScreenshotController


class DiagnosticTests(unittest.TestCase):
    def test_capture_exception_is_logged(self):
        controller = ScreenshotController()
        controller._on_drag_start(10, 10)
        with patch('stealth_screenshot.controller.ScreenCapture.capture', side_effect=OSError('capture failed')):
            with self.assertLogs('stealth_screenshot.controller', level='ERROR') as logs:
                controller._on_drag_end(100, 100)
        self.assertIn('capture_exception', '\n'.join(logs.output))

    def test_capture_failure_leaves_clipboard_untouched(self):
        controller = ScreenshotController()
        controller._on_drag_start(10, 10)
        with patch('stealth_screenshot.controller.ScreenCapture.capture', return_value=None), patch('stealth_screenshot.controller.ClipboardWriter.write_image') as write:
            with self.assertLogs('stealth_screenshot.controller', level='WARNING'):
                controller._on_drag_end(100, 100)
        write.assert_not_called()
