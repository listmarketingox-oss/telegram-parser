import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.keyword import MatchType


class KeywordCreate(BaseModel):
    pattern: str
    match_type: MatchType = MatchType.substring
    is_case_sensitive: bool = False


class KeywordResponse(BaseModel):
    id: uuid.UUID
    filter_set_id: uuid.UUID
    pattern: str
    match_type: MatchType
    is_case_sensitive: bool

    model_config = {"from_attributes": True}


class FilterSetCreate(BaseModel):
    name: str
    source_ids: list[uuid.UUID] = []
    date_from: datetime | None = None
    date_to: datetime | None = None


class FilterSetUpdate(BaseModel):
    name: str | None = None
    source_ids: list[uuid.UUID] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    is_active: bool | None = None


class FilterSetResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_ids: list[uuid.UUID]
    date_from: datetime | None
    date_to: datetime | None
    is_active: bool
    created_at: datetime
    keywords: list[KeywordResponse] = []

    model_config = {"from_attributes": True}
