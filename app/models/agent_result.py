"""Agent search results model."""
import datetime
import uuid

from sqlalchemy import Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AgentResult(UUIDMixin, Base):
    """Results from a single agent run."""

    __tablename__ = "agent_results"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    found_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matches: Mapped[list[dict]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()"
    )
