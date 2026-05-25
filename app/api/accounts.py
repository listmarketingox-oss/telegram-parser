import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.tg_account import AccountStatus, TgAccount
from app.models.user import AppUser
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AuthConfirmRequest,
    AuthStartResponse,
)
from app.services.encryption import decrypt, encrypt
from app.services.telethon_auth import confirm_auth, start_auth

router = APIRouter(
    prefix="/accounts",
    tags=["accounts"],
    dependencies=[Depends(get_current_user)],
)

_pending_hashes: dict[uuid.UUID, str] = {}


@router.get("", response_model=list[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TgAccount).order_by(TgAccount.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(body: AccountCreate, db: AsyncSession = Depends(get_db)):
    account = TgAccount(
        label=body.label,
        api_id=body.api_id,
        api_hash=encrypt(body.api_hash),
        phone=body.phone,
        status=AccountStatus.new,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(TgAccount).where(TgAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if body.label is not None:
        account.label = body.label
    await db.commit()
    await db.refresh(account)
    return account


@router.post("/{account_id}/auth/start", response_model=AuthStartResponse)
async def auth_start(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(TgAccount).where(TgAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    api_hash = decrypt(account.api_hash)
    try:
        temp_session, phone_code_hash = await start_auth(
            account.api_id, api_hash, account.phone
        )
    except Exception as e:
        account.status = AccountStatus.error
        account.last_error = str(e)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(e))

    account.session_string = encrypt(temp_session)
    account.status = AccountStatus.auth_pending
    _pending_hashes[account.id] = phone_code_hash
    await db.commit()
    return AuthStartResponse(message="Code sent", phone_code_hash=phone_code_hash)


@router.post("/{account_id}/auth/confirm", response_model=AccountResponse)
async def auth_confirm(
    account_id: uuid.UUID,
    body: AuthConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(TgAccount).where(TgAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.status != AccountStatus.auth_pending:
        raise HTTPException(status_code=400, detail="Account not in auth_pending state")

    phone_code_hash = _pending_hashes.get(account.id)
    if not phone_code_hash:
        raise HTTPException(status_code=400, detail="No pending auth — start auth first")

    api_hash = decrypt(account.api_hash)
    temp_session = decrypt(account.session_string)

    try:
        final_session = await confirm_auth(
            account.api_id,
            api_hash,
            account.phone,
            temp_session,
            phone_code_hash,
            body.code,
            body.password_2fa,
        )
    except Exception as e:
        account.status = AccountStatus.error
        account.last_error = str(e)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(e))

    account.session_string = encrypt(final_session)
    account.status = AccountStatus.active
    account.last_error = None
    _pending_hashes.pop(account.id, None)
    await db.commit()
    await db.refresh(account)
    return account
