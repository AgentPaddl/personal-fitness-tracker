"""Sanitizes an inbound `X-Request-Id` header before using it anywhere
(logs, forwarded headers, error responses).

An inbound request ID is untrusted caller input: never propagate control
characters, an unbounded length, or arbitrary content. Only a bounded,
safe ASCII token (ideally a UUID) is accepted as-is; anything else is
replaced with a freshly generated UUID.
"""

from __future__ import annotations

import re
import uuid

_SAFE_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def sanitize_request_id(raw: str | None) -> str:
    if raw and _SAFE_REQUEST_ID_PATTERN.match(raw):
        return raw
    return str(uuid.uuid4())
