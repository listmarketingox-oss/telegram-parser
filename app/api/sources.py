import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.job import Job, JobStatus, JobType
from app.models.source import Source
from app.models.tg_account import AccountStatus, TgAccount
from app.schemas.source import SourceCreate, SourceResponse, SourceUpdate
from app.services.encryption import decrypt
from app.services.source_resolver import resolve_source

router = APIRouter(
    prefix="/sources",
    tags=["sources"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Source).order_by(Source.created_at.desc())
    if is_active is not None:
        q = q.where(Source.is_active == is_active)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(body: SourceCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TgAccount).where(TgAccount.id == body.account_id))
    account = result.scalar_one_or_none()
    if not account or account.status != AccountStatus.active:
        raise HTTPException(status_code=400, detail="Account not found or not active")

    identifier = body.username or body.link
    if not identifier:
        raise HTTPException(status_code=400, detail="Provide username or link")

    try:
        info = await resolve_source(
            account.api_id,
            decrypt(account.api_hash),
            decrypt(account.session_string),
            identifier,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot resolve source: {e}")

    existing = await db.execute(
        select(Source).where(
            Source.account_id == account.id,
            Source.tg_entity_id == info["tg_entity_id"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Source already added for this account")

    source = Source(
        account_id=account.id,
        tg_entity_id=info["tg_entity_id"],
        username=info["username"],
        title=info["title"],
        type=info["type"],
        first_pass_until=body.first_pass_until,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    job = Job(type=JobType.first_pass, payload={"source_id": str(source.id)})
    db.add(job)
    await db.commit()

    return source


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: uuid.UUID,
    body: SourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if body.is_active is not None:
        source.is_active = body.is_active
    if body.first_pass_until is not None:
        source.first_pass_until = body.first_pass_until
    await db.commit()
    await db.refresh(source)
    return source


@router.post("/{source_id}/parse", status_code=status.HTTP_202_ACCEPTED)
async def trigger_parse(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    job = Job(type=JobType.parse_source, payload={"source_id": str(source.id)})
    db.add(job)
    await db.commit()
    return {"message": "Parse job queued"}


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_active = False
    await db.commit()
