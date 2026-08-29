"""Unit tests for image_validation.py's decompression-bomb handling.

Uses PIL.Image.MAX_IMAGE_PIXELS monkeypatching to deterministically trigger
Pillow's DecompressionBombWarning/DecompressionBombError on a tiny real
image, rather than committing or generating a huge decompression-bomb
fixture image.
"""

from __future__ import annotations

import warnings

from PIL import Image

from image_validation import image_content_matches_declared_type
from tests.image_fixtures import make_valid_jpeg_bytes, make_valid_png_bytes


def test_valid_jpeg_still_passes():
    assert image_content_matches_declared_type(make_valid_jpeg_bytes(), "image/jpeg") is True


def test_valid_png_still_passes():
    assert image_content_matches_declared_type(make_valid_png_bytes(), "image/png") is True


def test_decompression_bomb_warning_input_is_rejected(monkeypatch):
    # A pixel count strictly between the threshold and 2x the threshold
    # makes Pillow emit DecompressionBombWarning (not raise an error).
    image_bytes = make_valid_png_bytes(width=64, height=64)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 3000)

    assert image_content_matches_declared_type(image_bytes, "image/png") is False


def test_decompression_bomb_error_input_is_rejected(monkeypatch):
    # A pixel count more than 2x the threshold makes Pillow raise
    # DecompressionBombError outright.
    image_bytes = make_valid_png_bytes(width=64, height=64)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)

    assert image_content_matches_declared_type(image_bytes, "image/png") is False


def test_no_decompression_bomb_warning_escapes_the_validator(monkeypatch):
    image_bytes = make_valid_png_bytes(width=64, height=64)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 3000)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = image_content_matches_declared_type(image_bytes, "image/png")

    assert result is False
    assert not any(issubclass(w.category, Image.DecompressionBombWarning) for w in caught)
