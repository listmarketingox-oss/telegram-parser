import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.tg_account import AccountStatus


class AccountCreate(BaseModel):
    label: str
    api_id: int
    api_hash: str
    phone: str


class AccountUpdate(BaseModel):
    label: str | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    label: str
    api_id: int
    phone: str
    status: AccountStatus
    last_error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthStartRequest(BaseModel):
    pass


class AuthConfirmRequest(BaseModel):
    code: str
    password_2fa: str | None = None


class AuthStartResponse(BaseModel):
    message: str
    phone_code_hash: str
