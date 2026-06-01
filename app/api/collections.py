import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models.collection import Collection, CollectionItem
from app.models.source import Source

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
    dependencies=[Depends(get_current_user)],
)


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class AddSourceRequest(BaseModel):
    source_id: uuid.UUID


@router.get("")
async def list_collections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Collection)
        .options(selectinload(Collection.items).selectinload(CollectionItem.source))
        .order_by(Collection.created_at.desc())
    )
    collections = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "description": c.description,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "sources": [
                {
                    "id": str(item.source.id),
                    "title": item.source.title,
                    "username": item.source.username,
                    "type": item.source.type.value,
                    "item_id": str(item.id),
                }
                for item in c.items if item.source
            ],
        }
        for c in collections
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_collection(body: CollectionCreate, db: AsyncSession = Depends(get_db)):
    c = Collection(name=body.name, description=body.description)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return {"id": str(c.id), "name": c.name, "description": c.description}


@router.patch("/{coll_id}")
async def update_collection(
    coll_id: uuid.UUID, body: CollectionUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Collection).where(Collection.id == coll_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Collection not found")
    if body.name is not None:
        c.name = body.name
    if body.description is not None:
        c.description = body.description
    await db.commit()
    return {"id": str(c.id), "name": c.name}


@router.delete("/{coll_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(coll_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).where(Collection.id == coll_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Collection not found")
    await db.delete(c)
    await db.commit()


@router.post("/{coll_id}/sources", status_code=status.HTTP_201_CREATED)
async def add_source_to_collection(
    coll_id: uuid.UUID, body: AddSourceRequest, db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(
        select(CollectionItem).where(
            CollectionItem.collection_id == coll_id,
            CollectionItem.source_id == body.source_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Source already in collection")
    item = CollectionItem(collection_id=coll_id, source_id=body.source_id)
    db.add(item)
    await db.commit()
    return {"message": "ok"}


@router.delete("/{coll_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_source_from_collection(
    coll_id: uuid.UUID, source_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CollectionItem).where(
            CollectionItem.collection_id == coll_id,
            CollectionItem.source_id == source_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404)
    await db.delete(item)
    await db.commit()
