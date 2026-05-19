# Configuration has moved to app/core/config.py — this shim preserves backward compatibility.
# All new code should import from app.core.config directly.
from app.core.config import Settings, get_settings, settings  # noqa: F401

__all__ = ["Settings", "get_settings", "settings"]
