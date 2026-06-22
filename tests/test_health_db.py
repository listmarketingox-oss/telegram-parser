import pytest

from app import main


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, statement):
        self.statement = statement


class BrokenSession(FakeSession):
    async def execute(self, statement):
        raise RuntimeError("database unavailable")


@pytest.mark.asyncio
async def test_health_db_reports_connected(monkeypatch, client):
    monkeypatch.setattr(main, "async_session", lambda: FakeSession())

    resp = await client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "connected"}


@pytest.mark.asyncio
async def test_health_db_reports_error(monkeypatch, client):
    monkeypatch.setattr(main, "async_session", lambda: BrokenSession())

    resp = await client.get("/health/db")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
    assert "database unavailable" in resp.json()["db"]
