"""Verify native hooks install and stop without injecting user input."""
import time
import unittest

from stealth_screenshot.hotkey import HotkeyListener
from stealth_screenshot.mouse_hook import MouseHook


class HookStartupTests(unittest.TestCase):
    def test_native_hooks_start_and_stop(self):
        for hook in (HotkeyListener('ctrl+q', lambda: None),
                     MouseHook(lambda x, y: None, lambda x, y: None)):
            with self.subTest(hook=type(hook).__name__):
                try:
                    hook.start()
                    deadline = time.monotonic() + 2
                    while hook._hook_handle is None and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(hook._hook_handle, 'Native hook was not installed')
                    thread = hook._thread
                finally:
                    hook.stop()
                self.assertFalse(thread.is_alive(), 'Message pump did not stop')


if __name__ == '__main__':
    unittest.main()
