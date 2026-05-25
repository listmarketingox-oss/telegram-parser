from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import accounts, auth, filter_sets, jobs, matches, pages, sources, users

app = FastAPI(title="Telegram Parser", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(filter_sets.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(pages.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
