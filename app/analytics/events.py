from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ClickEvent:
    """Immutable value object representing a single click on a short URL."""

    short_url_id: uuid.UUID
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device: Optional[str] = None

    @property
    def visitor_hash(self) -> Optional[str]:
        """SHA-256 of IP + UA for unique visitor counting — no raw IP stored."""
        if self.ip_address and self.user_agent:
            raw = f"{self.ip_address}:{self.user_agent}"
            return hashlib.sha256(raw.encode()).hexdigest()
        return None

    def to_dict(self) -> dict:
        return {
            "short_url_id": str(self.short_url_id),
            "timestamp": self.timestamp.isoformat(),
            "visitor_hash": self.visitor_hash,
            "user_agent": self.user_agent,
            "referrer": self.referrer,
            "country": self.country,
            "city": self.city,
            "browser": self.browser,
            "os": self.os,
            "device": self.device,
        }
