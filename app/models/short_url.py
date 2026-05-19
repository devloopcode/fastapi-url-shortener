from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.click_event import ClickEvent
    from app.models.analytics_snapshot import AnalyticsSnapshot


class ShortURL(Base):
    __tablename__ = "short_urls"

    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    short_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    custom_alias: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Ownership
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Stats (denormalized for fast reads; authoritative count is in click_events)
    click_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Relationships
    owner: Mapped[Optional[User]] = relationship("User", back_populates="urls", lazy="noload")
    click_events: Mapped[list[ClickEvent]] = relationship(
        "ClickEvent", back_populates="short_url", lazy="noload"
    )
    snapshots: Mapped[list[AnalyticsSnapshot]] = relationship(
        "AnalyticsSnapshot", back_populates="short_url", lazy="noload"
    )

    __table_args__ = (
        Index("ix_short_urls_short_code", "short_code"),
        Index("ix_short_urls_owner_active", "owner_id", "is_active"),
        Index("ix_short_urls_expires_at", "expires_at"),
    )
