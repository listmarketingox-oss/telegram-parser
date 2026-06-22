import datetime
import uuid

import pytest

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.user import AppUser


def _user(email: str = "test@example.com") -> AppUser:
    return AppUser(
        id=uuid.uuid4(),
        email=email,
        password_hash="unused",
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_sets_cookie_and_logout_clears_cookie(client, monkeypatch):
    user = _user("login@example.com")

    async def fake_authenticate_user(db, email, password):
        assert email == "login@example.com"
        assert password == "secret"
        return user

    monkeypatch.setattr("app.api.auth.authenticate_user", fake_authenticate_user)
    app.dependency_overrides[get_db] = lambda: object()

    login = await client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "secret"},
    )
    assert login.status_code == 200
    assert login.json() == {"message": "ok"}
    assert "access_token" in client.cookies
    assert login.cookies["access_token"]

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"message": "ok"}
    assert "access_token" not in client.cookies


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(client, monkeypatch):
    async def fake_authenticate_user(db, email, password):
        return None

    monkeypatch.setattr("app.api.auth.authenticate_user", fake_authenticate_user)
    app.dependency_overrides[get_db] = lambda: object()

    resp = await client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "bad"},
    )
    assert resp.status_code == 401
    assert "access_token" not in client.cookies


@pytest.mark.asyncio
async def test_me_returns_current_user(client):
    user = _user("me@example.com")

    async def fake_current_user():
        return user

    app.dependency_overrides[get_current_user] = fake_current_user

    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"
