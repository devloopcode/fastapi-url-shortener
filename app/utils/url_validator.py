from __future__ import annotations

from urllib.parse import urlparse

# Block private/loopback ranges and well-known abuse targets
_BLOCKED_HOSTS = frozenset(
    [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "169.254.169.254",  # AWS metadata endpoint
        "metadata.google.internal",
    ]
)

_ALLOWED_SCHEMES = frozenset(["http", "https"])


def is_safe_url(url: str) -> bool:
    """
    Validates that a URL is safe to shorten.

    Rejects:
    - Non-HTTP/HTTPS schemes (prevents javascript:, file:, etc.)
    - Localhost / private network targets (prevents SSRF)
    - URLs without a valid host
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False

    host = parsed.hostname or ""
    if not host:
        return False

    if host in _BLOCKED_HOSTS:
        return False

    # Block private IPv4 ranges (simple string check — good enough for input validation)
    if host.startswith(("10.", "192.168.", "172.")):
        return False

    return True
