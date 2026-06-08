"""Live search API — parse all sources for a keyword right now + history."""
import csv
import io
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.search_history import SearchHistory
from app.services.live_parser import live_search
from app.services.query_expander import expand_query

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def search(
    keyword: str = Query(..., min_length=1),
    source_ids: str | None = Query(None),
    date_from: str | None = None,
    date_to: str | None = None,
    smart: bool = Query(True),
    limit: int = Query(500, ge=10, le=2000),
    db: AsyncSession = Depends(get_db),
):
    parsed_source_ids = None
    if source_ids:
        parsed_source_ids = [uuid.UUID(s.strip()) for s in source_ids.split(",") if s.strip()]

    parsed_date_from = datetime.fromisoformat(date_from) if date_from else None
    parsed_date_to = datetime.fromisoformat(date_to) if date_to else None

    # Smart search: expand query with related terms
    expanded_terms = None
    if smart:
        expanded_terms = await expand_query(keyword)

    results = await live_search(
        keyword=keyword,
        source_ids=parsed_source_ids,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        limit_per_source=limit,
        expanded_terms=expanded_terms,
    )

    # Save to history
    history = SearchHistory(
        keyword=keyword,
        results_count=len(results),
        results_data=results,
        date_from=date_from,
        date_to=date_to,
    )
    db.add(history)
    await db.commit()
    await db.refresh(history)

    return {
        "results": results,
        "total": len(results),
        "keyword": keyword,
        "expanded_terms": expanded_terms,
        "history_id": str(history.id),
    }


@router.get("/history")
async def search_history(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchHistory)
        .order_by(SearchHistory.created_at.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    return [
        {
            "id": str(h.id),
            "keyword": h.keyword,
            "results_count": h.results_count,
            "date_from": h.date_from,
            "date_to": h.date_to,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in items
    ]


@router.get("/history/{history_id}")
async def get_search_history(
    history_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchHistory).where(SearchHistory.id == history_id)
    )
    h = result.scalar_one_or_none()
    if not h:
        return {"error": "Not found"}
    return {
        "id": str(h.id),
        "keyword": h.keyword,
        "results_count": h.results_count,
        "results": h.results_data,
        "date_from": h.date_from,
        "date_to": h.date_to,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    }


@router.delete("/history/{history_id}")
async def delete_search_history(
    history_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchHistory).where(SearchHistory.id == history_id)
    )
    h = result.scalar_one_or_none()
    if h:
        await db.delete(h)
        await db.commit()
    return {"ok": True}


def _export_results(results: list, keyword: str, fmt: str):
    """Generate CSV or XLSX from results list."""
    try:
        headers = ["Канал", "Сообщение", "Ник", "Имя", "Телефон", "Ключ", "Дата и время", "Ссылка"]

        def _row(r):
            # Safely convert all fields to strings
            return [
                str(r.get("source_title", "")).strip(),
                str(r.get("message_text", "")).strip(),
                str(r.get("author_username") or "").strip(),
                str(r.get("author_display_name") or "").strip(),
                str(r.get("author_phone") or "").strip(),
                ", ".join(str(k) for k in (r.get("matched_keywords") or [])),
                str(r.get("posted_at", "")).strip(),
                str(r.get("message_link") or "").strip(),
            ]

        if fmt == "csv":
            # Use BytesIO with TextIOWrapper to handle UTF-8 properly
            output = io.BytesIO()
            text_wrapper = io.TextIOWrapper(output, encoding='utf-8', newline='')
            writer = csv.writer(text_wrapper, quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            for r in results:
                writer.writerow(_row(r))
            text_wrapper.flush()
            text_wrapper.detach()  # Detach wrapper to get BytesIO
            csv_bytes = output.getvalue()
            logger.info("Generated CSV: %d rows, %d bytes", len(results), len(csv_bytes))
            return Response(
                content=csv_bytes,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename=search_{keyword}.csv"},
            )

        # XLSX export
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for r in results:
            ws.append(_row(r))

        output = io.BytesIO()
        wb.save(output)
        xlsx_content = output.getvalue()
        logger.info("Generated XLSX: %d rows", len(results))

        return Response(
            content=xlsx_content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=search_{keyword}.xlsx"},
        )
    except Exception as e:
        logger.error("Export generation failed: %s", e, exc_info=True)
        raise


@router.get("/export/{history_id}")
async def export_from_history(
    history_id: uuid.UUID,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: AsyncSession = Depends(get_db),
):
    """Export saved search results by history ID."""
    try:
        result = await db.execute(
            select(SearchHistory).where(SearchHistory.id == history_id)
        )
        h = result.scalar_one_or_none()
        if not h:
            logger.warning("History not found: %s", history_id)
            raise HTTPException(status_code=404, detail="Результаты поиска не найдены")

        logger.info("Exporting %d results as %s", len(h.results_data or []), format)
        return _export_results(h.results_data or [], h.keyword, format)
    except Exception as e:
        logger.error("Export error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта: {str(e)}")
