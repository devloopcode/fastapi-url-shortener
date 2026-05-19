from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_BLOCKED_HOSTS = frozenset(
    [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "169.254.169.254",  # AWS/GCP IMDS endpoint
        "metadata.google.internal",
    ]
)

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),   # was "172." prefix — caught public IPs
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),        # IPv6 ULA
]

_ALLOWED_SCHEMES = frozenset(["http", "https"])


def is_safe_url(url: str) -> bool:
    """
    Validates that a URL is safe to shorten.

    Rejects:
    - Non-HTTP/HTTPS schemes (prevents javascript:, file:, data:, etc.)
    - Localhost / private network targets (prevents SSRF via RFC-1918 ranges)
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

    # Parse as IP address for precise range checking.
    # String-prefix checks (e.g. "172.") are unsafe: 172.99.x.x is public.
    try:
        addr = ipaddress.ip_address(host)
        if any(addr in net for net in _PRIVATE_NETWORKS):
            return False
    except ValueError:
        pass  # Not an IP address — hostname is fine

    return True
