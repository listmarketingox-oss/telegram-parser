import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class SearchHistory(UUIDMixin, Base):
    __tablename__ = "search_history"

    keyword: Mapped[str] = mapped_column(String)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    results_data: Mapped[dict] = mapped_column(JSONB, default=list)
    date_from: Mapped[str | None] = mapped_column(String, nullable=True)
    date_to: Mapped[str | None] = mapped_column(String, nullable=True)
    sources_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()"
    )
