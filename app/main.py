from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import accounts, auth, filter_sets, jobs, matches, pages, search, sources, users
from app.database import async_session

app = FastAPI(title="Telegram Parser", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(filter_sets.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(pages.router)


@app.get("/health")
async def health():
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}
