import datetime
import enum

from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class AccountStatus(str, enum.Enum):
    new = "new"
    auth_pending = "auth_pending"
    active = "active"
    flood_wait = "flood_wait"
    banned = "banned"
    error = "error"


class TgAccount(UUIDMixin, Base):
    __tablename__ = "tg_accounts"

    label: Mapped[str] = mapped_column(String)
    api_id: Mapped[int] = mapped_column(Integer)
    api_hash: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(String)
    session_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus), default=AccountStatus.new
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()"
    )

    sources = relationship("Source", back_populates="account")
