"""Clipboard writer — puts the captured image into the Windows clipboard.

Writes both CF_DIB (native bitmap) and PNG format for maximum app
compatibility.
"""

import ctypes
import io
from ctypes import wintypes
from typing import Optional

from PIL import Image

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Clipboard format constants
CF_DIB = 8
GMEM_MOVEABLE = 0x0002

# LockClipboard / UnlockClipboard
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wintypes.UINT

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
kernel32.GlobalFree.restype = wintypes.HANDLE


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class ClipboardWriter:
    """Writes a Pillow Image to the clipboard in CF_DIB + PNG format."""

    @staticmethod
    def write_image(img: Image.Image) -> bool:
        """Copy *img* to the clipboard. Returns True on success."""
        # Prepare DIB data (BITMAPINFOHEADER + BGRA pixel data)
        rgba = img.convert("RGBA")
        w, h = rgba.size

        # Flatten to BGRA bottom-up (DIB convention: positive biHeight)
        # Pillow gives top-down RGBA; flip vertically and swap R/B
        bgra = bytearray(w * h * 4)
        pixels = rgba.load()
        for row in range(h):
            src_row = h - 1 - row  # flip vertically for bottom-up DIB
            for col in range(w):
                r, g, b, a = pixels[col, src_row]
                idx = (row * w + col) * 4
                bgra[idx] = b
                bgra[idx + 1] = g
                bgra[idx + 2] = r
                bgra[idx + 3] = a

        bih = BITMAPINFOHEADER()
        bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bih.biWidth = w
        bih.biHeight = h  # positive → bottom-up
        bih.biPlanes = 1
        bih.biBitCount = 32
        bih.biCompression = 0  # BI_RGB
        bih.biSizeImage = w * h * 4

        dib_bytes = bytes(bih) + bytes(bgra)

        # Prepare PNG bytes
        png_buf = io.BytesIO()
        rgba.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        # Register PNG clipboard format
        cf_png = user32.RegisterClipboardFormatW("PNG")

        # Open clipboard and write
        if not user32.OpenClipboard(0):
            return False

        try:
            user32.EmptyClipboard()

            # Write CF_DIB
            h_dib = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib_bytes))
            if h_dib:
                ptr = kernel32.GlobalLock(h_dib)
                if ptr:
                    ctypes.memmove(ptr, dib_bytes, len(dib_bytes))
                    kernel32.GlobalUnlock(h_dib)
                    user32.SetClipboardData(CF_DIB, h_dib)
                    # System owns the memory now; do not free

            # Write PNG
            if cf_png:
                h_png = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(png_bytes))
                if h_png:
                    ptr = kernel32.GlobalLock(h_png)
                    if ptr:
                        ctypes.memmove(ptr, png_bytes, len(png_bytes))
                        kernel32.GlobalUnlock(h_png)
                        user32.SetClipboardData(cf_png, h_png)

            return True

        except Exception:
            return False

        finally:
            user32.CloseClipboard()
