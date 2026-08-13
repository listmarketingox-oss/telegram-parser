"""Tests for live_parser session-death handling.

Regression: a revoked/invalid Telegram session used to be swallowed silently in
live_search, so search returned an empty list and the account still showed
"active". Now such accounts are flipped to status=error so the failure is visible
and the user is told to re-authorize.
"""
from app.models.tg_account import AccountStatus
from app.services import live_parser
from app.services.live_parser import _is_session_dead_error, _mark_accounts_dead


# Exception classes named exactly like the telethon/fernet errors we detect.
class AuthKeyUnregisteredError(Exception):
    pass


class InvalidToken(Exception):
    pass


class FloodWaitError(Exception):
    pass


def test_is_session_dead_error_true_for_known_errors():
    assert _is_session_dead_error(AuthKeyUnregisteredError())
    assert _is_session_dead_error(InvalidToken())


def test_is_session_dead_error_false_for_unrelated_errors():
    assert not _is_session_dead_error(FloodWaitError())
    assert not _is_session_dead_error(ValueError("boom"))


class _FakeAccount:
    def __init__(self, label, status, last_error=None):
        self.label = label
        self.status = status
        self.last_error = last_error


class _FakeDB:
    def __init__(self, account):
        self._account = account
        self.committed = False

    async def get(self, model, account_id):
        return self._account

    async def commit(self):
        self.committed = True


class _FakeSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *exc):
        return False


async def test_mark_accounts_dead_flips_active_to_error(monkeypatch):
    account = _FakeAccount("@onikXA", AccountStatus.active)
    db = _FakeDB(account)
    monkeypatch.setattr(live_parser, "async_session", lambda: _FakeSessionCtx(db))

    await _mark_accounts_dead({"id-1": "Сессия недействительна"})

    assert account.status == AccountStatus.error
    assert account.last_error == "Сессия недействительна"
    assert db.committed


async def test_mark_accounts_dead_does_not_clobber_existing_error(monkeypatch):
    account = _FakeAccount("@onikXA", AccountStatus.error, last_error="original")
    db = _FakeDB(account)
    monkeypatch.setattr(live_parser, "async_session", lambda: _FakeSessionCtx(db))

    await _mark_accounts_dead({"id-1": "new message"})

    assert account.last_error == "original"


async def test_mark_accounts_dead_noop_when_nothing_dead(monkeypatch):
    def _boom():
        raise AssertionError("must not open a DB session when there is nothing to mark")

    monkeypatch.setattr(live_parser, "async_session", _boom)

    await _mark_accounts_dead({})  # should return early without touching the DB
