import datetime
import enum
import uuid

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class SourceType(str, enum.Enum):
    channel = "channel"
    group = "group"
    private_channel = "private_channel"
    private_group = "private_group"


class Source(UUIDMixin, Base):
    __tablename__ = "sources"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tg_accounts.id")
    )
    tg_entity_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    type: Mapped[SourceType] = mapped_column(Enum(SourceType))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_parsed_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    first_pass_done: Mapped[bool] = mapped_column(Boolean, default=False)
    first_pass_until: Mapped[datetime.datetime | None] = mapped_column(
        nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()"
    )

    account = relationship("TgAccount", back_populates="sources")
    matches = relationship("Match", back_populates="source")
