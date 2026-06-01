import datetime
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class Collection(UUIDMixin, Base):
    """A named folder/project grouping sources together."""
    __tablename__ = "collections"

    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default="now()")

    items = relationship("CollectionItem", back_populates="collection", cascade="all, delete-orphan")


class CollectionItem(UUIDMixin, Base):
    """Link between a collection and a source."""
    __tablename__ = "collection_items"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE")
    )

    collection = relationship("Collection", back_populates="items")
    source = relationship("Source")
