import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.match import Match
from app.schemas.match import MatchListResponse, MatchResponse

router = APIRouter(
    prefix="/matches",
    tags=["matches"],
    dependencies=[Depends(get_current_user)],
)


def _apply_filters(q, source_id, filter_set_id, date_from, date_to, keyword, author_username, search):
    if source_id:
        q = q.where(Match.source_id == source_id)
    if filter_set_id:
        q = q.where(Match.filter_set_id == filter_set_id)
    if date_from:
        q = q.where(Match.posted_at >= date_from)
    if date_to:
        q = q.where(Match.posted_at <= date_to)
    if keyword:
        q = q.where(Match.matched_keywords.any(keyword))
    if author_username:
        q = q.where(Match.author_username == author_username)
    if search:
        q = q.where(Match.message_text.ilike(f"%{search}%"))
    return q


@router.get("", response_model=MatchListResponse)
async def list_matches(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    source_id: uuid.UUID | None = None,
    filter_set_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    keyword: str | None = None,
    author_username: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(Match)
    base = _apply_filters(base, source_id, filter_set_id, date_from, date_to, keyword, author_username, search)

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = base.order_by(Match.posted_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)

    return MatchListResponse(
        items=result.scalars().all(),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export", response_class=StreamingResponse)
async def export_matches(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    source_id: uuid.UUID | None = None,
    filter_set_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    keyword: str | None = None,
    author_username: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Match)
    q = _apply_filters(q, source_id, filter_set_id, date_from, date_to, keyword, author_username, search)
    q = q.order_by(Match.posted_at.desc()).limit(10000)
    result = await db.execute(q)
    matches = result.scalars().all()

    headers = [
        "posted_at", "source_id", "message_id", "message_link",
        "author_username", "author_display_name", "message_text",
        "matched_keywords",
    ]

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        for m in matches:
            writer.writerow([
                m.posted_at.isoformat(),
                str(m.source_id),
                m.message_id,
                m.message_link or "",
                m.author_username or "",
                m.author_display_name or "",
                m.message_text,
                ", ".join(m.matched_keywords),
            ])
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=matches.csv"},
        )

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for m in matches:
        ws.append([
            m.posted_at.isoformat(),
            str(m.source_id),
            m.message_id,
            m.message_link or "",
            m.author_username or "",
            m.author_display_name or "",
            m.message_text,
            ", ".join(m.matched_keywords),
        ])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=matches.xlsx"},
    )


@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(match_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match
