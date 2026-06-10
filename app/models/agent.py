"""Autonomous monitoring agent model."""
import datetime
import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class Agent(UUIDMixin, Base):
    """Autonomous agent for periodic keyword monitoring."""

    __tablename__ = "agents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    source_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    collection_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    search_mode: Mapped[str] = mapped_column(
        String(20), default="smart", nullable=False
    )
    cron_schedule: Mapped[str] = mapped_column(
        String(100), default="0 8-20 * * *", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_run_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=True
    )
    results_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()", onupdate=datetime.datetime.utcnow
    )
