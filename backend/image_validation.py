"""Real image-content validation, not just trusting the declared MIME type.

Uses Pillow to inspect actual bytes: rejects corrupt/truncated images and
images whose real format does not match the declared MIME type (e.g. a PNG
uploaded with `Content-Type: image/jpeg`).
"""

from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError

#: Maps our supported public MIME types to the Pillow format name actually
#: written into a well-formed file of that type.
_MIME_TYPE_TO_PIL_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG"}


def image_content_matches_declared_type(data: bytes, declared_mime_type: str) -> bool:
    """Returns True only if `data` decodes as a valid, non-truncated image
    whose actual format matches `declared_mime_type`. Never raises: any
    decode failure is treated as "does not match" (untrusted input).
    """

    expected_format = _MIME_TYPE_TO_PIL_FORMAT.get(declared_mime_type)
    if expected_format is None:
        return False

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, EOFError):
        return False

    # Image.verify() leaves the image object unusable for further access,
    # so the format is read from a freshly (re)opened image instead.
    try:
        with Image.open(io.BytesIO(data)) as image:
            detected_format = image.format
    except (UnidentifiedImageError, OSError, ValueError, EOFError):
        return False

    return detected_format == expected_format
