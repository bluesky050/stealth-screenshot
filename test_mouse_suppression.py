"""Exercise the hook callback without sending input to the desktop."""
import ctypes
import unittest
from unittest.mock import Mock, patch
from stealth_screenshot import mouse_hook as module


class MouseSuppressionTests(unittest.TestCase):
    def exercise(self, armed):
        start, end = Mock(), Mock()
        hook = module.MouseHook(start, end)
        native = Mock()
        native.CallNextHookEx.return_value = 0
        results = []

        def install(kind, callback, handle, thread):
            if armed:
                hook.arm()
            for event, x, y in [(module.WM_LBUTTONDOWN, 10, 20),
                                 (module.WM_LBUTTONUP, 110, 120)]:
                info = module.MSLLHOOKSTRUCT()
                info.pt.x, info.pt.y = x, y
                results.append(callback(0, event, ctypes.addressof(info)))
            return 1

        native.SetWindowsHookExW.side_effect = install
        with patch.object(module, 'user32', native):
            hook._hook_loop()
        return results, start, end, native, hook

    def test_capture_clicks_do_not_reach_desktop(self):
        results, start, end, native, hook = self.exercise(True)
        self.assertEqual(results, [1, 1])
        native.CallNextHookEx.assert_not_called()
        start.assert_called_once_with(10, 20)
        end.assert_called_once_with(110, 120)
        self.assertFalse(hook.is_armed())

    def test_normal_clicks_pass_through(self):
        results, start, end, native, hook = self.exercise(False)
        self.assertEqual(results, [0, 0])
        self.assertEqual(native.CallNextHookEx.call_count, 2)
        start.assert_not_called()
        end.assert_not_called()


if __name__ == '__main__':
    unittest.main()
