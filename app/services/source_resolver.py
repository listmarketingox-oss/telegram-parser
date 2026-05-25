"""Resolve a Telegram username/link to entity info using Telethon."""
import logging
import re

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat

from app.models.source import SourceType

logger = logging.getLogger(__name__)


def _classify(entity) -> SourceType:
    if isinstance(entity, Channel):
        if entity.megagroup:
            return SourceType.group if getattr(entity, "username", None) else SourceType.private_group
        return SourceType.channel if getattr(entity, "username", None) else SourceType.private_channel
    if isinstance(entity, Chat):
        return SourceType.group
    return SourceType.group


def _extract_username(text: str) -> str:
    text = text.strip().rstrip("/")
    match = re.search(r"(?:t\.me/|@)([a-zA-Z0-9_]+)", text)
    if match:
        return match.group(1)
    return text


async def resolve_source(
    api_id: int,
    api_hash: str,
    session_string: str,
    identifier: str,
) -> dict:
    """Returns dict with tg_entity_id, username, title, type."""
    username = _extract_username(identifier)
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    try:
        entity = await client.get_entity(username)
        return {
            "tg_entity_id": entity.id,
            "username": getattr(entity, "username", None),
            "title": getattr(entity, "title", username),
            "type": _classify(entity),
        }
    finally:
        await client.disconnect()
