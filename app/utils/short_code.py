from __future__ import annotations

import secrets
import string

from app.config import settings

_ALPHABET = string.ascii_letters + string.digits  # base62


def generate_short_code(length: int | None = None) -> str:
    """
    Generate a cryptographically random base62 short code.

    Using secrets.choice over random.choice ensures the output is
    unpredictable — important for preventing enumeration attacks on
    private links.
    """
    n = length or settings.SHORT_CODE_LENGTH
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))
