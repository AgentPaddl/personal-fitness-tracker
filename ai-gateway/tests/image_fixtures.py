"""Shared, deterministic, non-sensitive test image fixtures.

Built with Pillow so validators that inspect actual image bytes (not just a
declared MIME type) have something real to accept, and something
deliberately broken to reject.
"""

from __future__ import annotations

import io

from PIL import Image


def make_valid_jpeg_bytes(width: int = 8, height: int = 8) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 60, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def make_valid_png_bytes(width: int = 8, height: int = 8) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(40, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def make_truncated_jpeg_bytes() -> bytes:
    return make_valid_jpeg_bytes()[:20]


def make_truncated_png_bytes() -> bytes:
    return make_valid_png_bytes()[:20]


def make_tail_truncated_jpeg_bytes() -> bytes:
    """A structurally valid-looking JPEG (readable headers) missing tens of
    trailing bytes (scan data / EOI marker) - the case `Image.verify()`
    alone lets through but a full `.load()` decode catches.
    """
    data = make_valid_jpeg_bytes(width=32, height=32)
    return data[:-40]


def make_tail_truncated_png_bytes() -> bytes:
    """A structurally valid-looking PNG missing only its final few bytes
    (part of the trailing IEND chunk) - pixel data itself is intact, so
    this is only caught by an explicit IEND-completeness check, not by
    `.load()` alone.
    """
    data = make_valid_png_bytes(width=32, height=32)
    return data[:-3]
