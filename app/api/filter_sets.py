import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models.filter_set import FilterSet
from app.models.keyword import Keyword
from app.schemas.filter_set import (
    FilterSetCreate,
    FilterSetResponse,
    FilterSetUpdate,
    KeywordCreate,
    KeywordResponse,
)

router = APIRouter(
    prefix="/filter-sets",
    tags=["filter-sets"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[FilterSetResponse])
async def list_filter_sets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FilterSet)
        .options(selectinload(FilterSet.keywords))
        .order_by(FilterSet.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=FilterSetResponse, status_code=status.HTTP_201_CREATED)
async def create_filter_set(body: FilterSetCreate, db: AsyncSession = Depends(get_db)):
    fs = FilterSet(
        name=body.name,
        source_ids=body.source_ids,
        date_from=body.date_from,
        date_to=body.date_to,
    )
    db.add(fs)
    await db.commit()
    await db.refresh(fs, ["keywords"])
    return fs


@router.patch("/{fs_id}", response_model=FilterSetResponse)
async def update_filter_set(
    fs_id: uuid.UUID,
    body: FilterSetUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FilterSet).options(selectinload(FilterSet.keywords)).where(FilterSet.id == fs_id)
    )
    fs = result.scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="Filter set not found")
    if body.name is not None:
        fs.name = body.name
    if body.source_ids is not None:
        fs.source_ids = body.source_ids
    if body.date_from is not None:
        fs.date_from = body.date_from
    if body.date_to is not None:
        fs.date_to = body.date_to
    if body.is_active is not None:
        fs.is_active = body.is_active
    await db.commit()
    await db.refresh(fs, ["keywords"])
    return fs


@router.delete("/{fs_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter_set(fs_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FilterSet).where(FilterSet.id == fs_id))
    fs = result.scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="Filter set not found")
    await db.delete(fs)
    await db.commit()


@router.get("/{fs_id}/keywords", response_model=list[KeywordResponse])
async def list_keywords(fs_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.filter_set_id == fs_id))
    return result.scalars().all()


@router.post(
    "/{fs_id}/keywords",
    response_model=KeywordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_keyword(
    fs_id: uuid.UUID,
    body: KeywordCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(FilterSet).where(FilterSet.id == fs_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Filter set not found")
    kw = Keyword(
        filter_set_id=fs_id,
        pattern=body.pattern,
        match_type=body.match_type,
        is_case_sensitive=body.is_case_sensitive,
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw


@router.delete("/{fs_id}/keywords/{kw_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    fs_id: uuid.UUID,
    kw_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Keyword).where(Keyword.id == kw_id, Keyword.filter_set_id == fs_id)
    )
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(kw)
    await db.commit()
