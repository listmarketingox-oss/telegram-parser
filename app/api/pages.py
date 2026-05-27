"""Server-side rendered pages using Jinja2."""
from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from starlette.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.match import Match
from app.models.source import Source
from app.models.tg_account import TgAccount
from app.services.auth import decode_access_token

router = APIRouter(tags=["pages"])
_env = Environment(loader=FileSystemLoader("templates"), auto_reload=True, cache_size=0)
templates = Jinja2Templates(env=_env)


def _check_auth(access_token: str | None) -> bool:
    if not access_token:
        return False
    return decode_access_token(access_token) is not None


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, access_token: str | None = Cookie(default=None)):
    if not _check_auth(access_token):
        return RedirectResponse("/login")
    return RedirectResponse("/dashboard")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not _check_auth(access_token):
        return RedirectResponse("/login")

    accounts_count = (await db.execute(select(func.count()).select_from(TgAccount))).scalar() or 0
    sources_active = (await db.execute(
        select(func.count()).select_from(Source).where(Source.is_active == True)
    )).scalar() or 0
    matches_total = (await db.execute(select(func.count()).select_from(Match))).scalar() or 0

    recent = await db.execute(
        select(Match).order_by(Match.collected_at.desc()).limit(10)
    )
    recent_matches = recent.scalars().all()

    return templates.TemplateResponse(request, "dashboard.html", context={
        "accounts_count": accounts_count,
        "sources_active": sources_active,
        "matches_total": matches_total,
        "recent_matches": recent_matches,
    })


@router.get("/accounts-page", response_class=HTMLResponse)
async def accounts_page(request: Request, access_token: str | None = Cookie(default=None)):
    if not _check_auth(access_token):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "accounts.html")


@router.get("/sources-page", response_class=HTMLResponse)
async def sources_page(request: Request, access_token: str | None = Cookie(default=None)):
    if not _check_auth(access_token):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "sources.html")


@router.get("/filters-page", response_class=HTMLResponse)
async def filters_page(request: Request, access_token: str | None = Cookie(default=None)):
    if not _check_auth(access_token):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "filters.html")


@router.get("/results-page", response_class=HTMLResponse)
async def results_page(request: Request, access_token: str | None = Cookie(default=None)):
    if not _check_auth(access_token):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "results.html")
