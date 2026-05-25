import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.source import SourceType


class SourceCreate(BaseModel):
    account_id: uuid.UUID
    username: str | None = None
    link: str | None = None
    first_pass_until: datetime | None = None


class SourceUpdate(BaseModel):
    is_active: bool | None = None
    first_pass_until: datetime | None = None


class SourceResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    tg_entity_id: int
    username: str | None
    title: str
    type: SourceType
    is_active: bool
    last_parsed_message_id: int | None
    first_pass_done: bool
    first_pass_until: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
