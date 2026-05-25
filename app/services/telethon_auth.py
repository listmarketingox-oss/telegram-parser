"""Telethon authorization helpers.

Handles the two-step auth flow:
1. start_auth — sends code to phone, returns phone_code_hash
2. confirm_auth — signs in with code (+ optional 2FA), returns StringSession
"""
import logging

from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


async def start_auth(api_id: int, api_hash: str, phone: str) -> tuple[str, str]:
    """Send auth code to phone. Returns (session_string, phone_code_hash)."""
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    result = await client.send_code_request(phone)
    session_str = client.session.save()
    await client.disconnect()
    return session_str, result.phone_code_hash


async def confirm_auth(
    api_id: int,
    api_hash: str,
    phone: str,
    session_string: str,
    phone_code_hash: str,
    code: str,
    password_2fa: str | None = None,
) -> str:
    """Sign in with code + optional 2FA. Returns final StringSession."""
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except Exception:
        if password_2fa:
            await client.sign_in(password=password_2fa)
        else:
            await client.disconnect()
            raise

    final_session = client.session.save()
    await client.disconnect()
    return final_session
