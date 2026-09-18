"""Screen capture using Win32 BitBlt with DPI-aware physical pixels."""

import ctypes
import io
from ctypes import wintypes
from typing import Optional

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Win32 constants
SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0
CAPTUREBLT = 0x40000000  # include layered windows

# GetSystemMetrics indices
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),  # negative = top-down
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class ScreenCapture:
    """Captures a rectangular region of the virtual screen using BitBlt."""

    @staticmethod
    def capture(rect: tuple[int, int, int, int]) -> Optional[Image.Image]:
        """Capture (x, y, width, height) from the virtual screen.

        Coordinates are in virtual-screen space (origin at top-left of
        the leftmost monitor).  Returns a Pillow Image or None on failure.
        """
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return None

        # Clamp to virtual screen bounds
        vs_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vs_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vs_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vs_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        if vs_w == 0 or vs_h == 0:
            return None

        x = max(x, vs_x)
        y = max(y, vs_y)
        w = min(w, vs_w - (x - vs_x))
        h = min(h, vs_h - (y - vs_y))
        if w <= 0 or h <= 0:
            return None

        # Source DC — entire virtual screen
        src_dc = user32.GetDC(0)
        if not src_dc:
            return None

        mem_dc = gdi32.CreateCompatibleDC(src_dc)
        if not mem_dc:
            user32.ReleaseDC(0, src_dc)
            return None

        bmp = gdi32.CreateCompatibleBitmap(src_dc, w, h)
        if not bmp:
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(0, src_dc)
            return None

        old_bmp = gdi32.SelectObject(mem_dc, bmp)

        try:
            # BitBlt from screen to memory DC
            if not gdi32.BitBlt(mem_dc, 0, 0, w, h, src_dc, x, y, SRCCOPY | CAPTUREBLT):
                return None

            # Extract pixels via GetDIBits (top-down BGRA)
            bi = BITMAPINFOHEADER()
            bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bi.biWidth = w
            bi.biHeight = -h  # negative → top-down
            bi.biPlanes = 1
            bi.biBitCount = 32
            bi.biCompression = BI_RGB
            bi.biSizeImage = w * h * 4

            buf = ctypes.create_string_buffer(w * h * 4)
            bi_full = BITMAPINFO()
            bi_full.bmiHeader = bi

            rows = gdi32.GetDIBits(
                mem_dc, bmp, 0, h,
                buf, ctypes.byref(bi_full), DIB_RGB_COLORS
            )
            if rows == 0:
                return None

            # Construct Pillow image from raw BGRA buffer
            img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1)
            return img.copy()  # detach from the ctypes buffer

        finally:
            gdi32.SelectObject(mem_dc, old_bmp)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(0, src_dc)
