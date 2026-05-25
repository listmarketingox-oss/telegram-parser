import datetime
import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class FilterSet(UUIDMixin, Base):
    __tablename__ = "filter_sets"

    name: Mapped[str] = mapped_column(String)
    source_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list
    )
    date_from: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    date_to: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()"
    )

    keywords = relationship("Keyword", back_populates="filter_set", cascade="all, delete-orphan")
