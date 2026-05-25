import datetime
import enum

from sqlalchemy import Enum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class JobType(str, enum.Enum):
    parse_source = "parse_source"
    first_pass = "first_pass"
    reauth = "reauth"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Job(UUIDMixin, Base):
    __tablename__ = "jobs"

    type: Mapped[JobType] = mapped_column(Enum(JobType))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.queued
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default="now()", onupdate=datetime.datetime.utcnow
    )
