from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Date, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.short_url import ShortURL


class AnalyticsSnapshot(Base):
    """
    Daily aggregated analytics per short URL.
    Written by the background aggregation worker to keep reporting fast
    without scanning the full click_events table on every dashboard request.
    """

    __tablename__ = "analytics_snapshots"

    short_url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("short_urls.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    total_clicks: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    unique_visitors: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # JSON blobs for dimension breakdowns  {dimension_value: count}
    country_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    browser_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    os_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    device_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    referrer_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    short_url: Mapped[ShortURL] = relationship(
        "ShortURL", back_populates="snapshots", lazy="noload"
    )

    __table_args__ = (
        UniqueConstraint("short_url_id", "snapshot_date", name="uq_snapshot_url_date"),
        Index("ix_snapshots_url_date", "short_url_id", "snapshot_date"),
    )
