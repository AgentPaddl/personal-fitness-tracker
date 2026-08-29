"""Shared, deterministic, non-sensitive test image fixtures for backend tests."""

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
