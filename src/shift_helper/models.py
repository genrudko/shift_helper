"""Database models for Shift-Helper."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative model base."""


class Event(Base):
    """Structured operational event stored in the local journal."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    asset_label: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[str | None] = mapped_column(Text)
    performer: Mapped[str | None] = mapped_column(String(160))
    author: Mapped[str | None] = mapped_column(String(160))
    error_codes: Mapped[str | None] = mapped_column(String(255))
    rotor_limit: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    repair_power_mw: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    # The physical SQLite column keeps its prototype name for backward compatibility.
    downtime_losses_rub: Mapped[Decimal | None] = mapped_column(
        "losses_mwh",
        Numeric(12, 2),
    )
    end_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    include_in_report: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class DeletedEvent(Base):
    """Immutable snapshot retained when an operator deletes a journal row."""

    __tablename__ = "deleted_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_event_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
