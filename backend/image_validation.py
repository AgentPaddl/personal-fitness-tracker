"""Real image-content validation, not just trusting the declared MIME type.

Uses Pillow to inspect actual bytes: rejects corrupt/truncated images and
images whose real format does not match the declared MIME type (e.g. a PNG
uploaded with `Content-Type: image/jpeg`).
"""

from __future__ import annotations

import io
import warnings

from PIL import Image, UnidentifiedImageError

#: Maps our supported public MIME types to the Pillow format name actually
#: written into a well-formed file of that type.
_MIME_TYPE_TO_PIL_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG"}

#: Exceptions Pillow raises for corrupt/truncated/oversized image data.
#: `DecompressionBombError` is not an `OSError` subclass, so it must be
#: listed explicitly. `DecompressionBombWarning` is only ever *emitted*
#: (never raised) by Pillow itself; it is turned into a real exception via
#: `warnings.simplefilter("error", ...)` below so a borderline-oversized
#: image is rejected rather than silently accepted with a warning.
_PILLOW_INVALID_IMAGE_EXCEPTIONS = (
    UnidentifiedImageError,
    OSError,
    ValueError,
    EOFError,
    Image.DecompressionBombError,
    Image.DecompressionBombWarning,
)

#: A well-formed PNG always ends with an empty IEND chunk: 4-byte zero
#: length + "IEND" + its fixed CRC (the CRC of "IEND" plus no data is
#: always this same constant). Pillow's `.load()` decodes all pixel data
#: from the preceding IDAT chunk(s) and does not itself require IEND to be
#: present, so a file missing only this trailing chunk decodes "successfully"
#: despite being truncated. Checked explicitly as a format-specific
#: completeness guard that `.load()` alone cannot provide.
_PNG_IEND_CHUNK = b"\x00\x00\x00\x00IEND\xaeB\x60\x82"


def image_content_matches_declared_type(data: bytes, declared_mime_type: str) -> bool:
    """Returns True only if `data` decodes as a valid, non-truncated image
    whose actual format matches `declared_mime_type`. Never raises: any
    decode failure (including a tail-truncated file that only fails during
    full pixel decoding, not header parsing) is treated as "does not
    match" (untrusted input).
    """

    expected_format = _MIME_TYPE_TO_PIL_FORMAT.get(declared_mime_type)
    if expected_format is None:
        return False

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except _PILLOW_INVALID_IMAGE_EXCEPTIONS:
        return False

    # image.verify() leaves the file object unusable for further access,
    # and critically does not itself force a full pixel decode - it only
    # checks that the file structure is well-formed, so a file truncated
    # only near its tail (e.g. missing JPEG scan data/EOI marker) can still
    # pass it. Re-open and call load() to force an actual full decode,
    # which is what catches that case.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                detected_format = image.format
                image.load()
    except _PILLOW_INVALID_IMAGE_EXCEPTIONS:
        return False

    if expected_format == "PNG" and not data.endswith(_PNG_IEND_CHUNK):
        # A PNG's pixel data lives entirely in the IDAT chunk(s) before
        # IEND, so a file missing only its trailing IEND chunk still
        # decodes "successfully" above despite being truncated.
        return False

    return detected_format == expected_format
