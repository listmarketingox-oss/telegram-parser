import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class MatchType(str, enum.Enum):
    substring = "substring"
    whole_word = "whole_word"
    regex = "regex"


class Keyword(UUIDMixin, Base):
    __tablename__ = "keywords"

    filter_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filter_sets.id", ondelete="CASCADE")
    )
    pattern: Mapped[str] = mapped_column(String)
    match_type: Mapped[MatchType] = mapped_column(
        Enum(MatchType), default=MatchType.substring
    )
    is_case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)

    filter_set = relationship("FilterSet", back_populates="keywords")
