import uuid
from datetime import datetime

from pydantic import BaseModel


class MatchResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    filter_set_id: uuid.UUID | None
    message_id: int
    message_link: str | None
    message_text: str
    matched_keywords: list[str]
    author_user_id: int | None
    author_username: str | None
    author_display_name: str | None
    posted_at: datetime
    collected_at: datetime

    model_config = {"from_attributes": True}


class MatchListResponse(BaseModel):
    items: list[MatchResponse]
    total: int
    page: int
    page_size: int
