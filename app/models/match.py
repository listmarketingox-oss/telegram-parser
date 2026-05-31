import datetime
import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class Match(UUIDMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("source_id", "message_id", "filter_set_id", name="uq_match"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id")
    )
    filter_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filter_sets.id"), nullable=True
    )
    message_id: Mapped[int] = mapped_column(BigInteger)
    message_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_text: Mapped[str] = mapped_column(Text)
    matched_keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    author_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    author_username: Mapped[str | None] = mapped_column(String, nullable=True)
    author_display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    author_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String, nullable=True)
    posted_at: Mapped[datetime.datetime]
    collected_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()"
    )

    source = relationship("Source", back_populates="matches")
