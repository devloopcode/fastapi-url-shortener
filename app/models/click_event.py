from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.short_url import ShortURL


class ClickEvent(Base):
    __tablename__ = "click_events"

    short_url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("short_urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Visitor fingerprint (hashed IP for privacy)
    visitor_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Geo data (resolved asynchronously)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Request metadata
    referrer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Parsed UA fields (stored for fast analytics aggregation)
    browser: Mapped[str | None] = mapped_column(String(50), nullable=True)
    os: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device: Mapped[str | None] = mapped_column(String(20), nullable=True)

    short_url: Mapped[ShortURL] = relationship(
        "ShortURL", back_populates="click_events", lazy="noload"
    )

    __table_args__ = (
        # Critical index for analytics time-range queries
        Index("ix_click_events_url_created", "short_url_id", "created_at"),
        Index("ix_click_events_created_at", "created_at"),
        Index("ix_click_events_country", "country"),
    )
