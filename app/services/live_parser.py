"""Live parser — searches all active sources for a keyword right now."""
import asyncio
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from app.database import async_session
from app.models.source import Source
from app.models.tg_account import AccountStatus, TgAccount
from app.services.encryption import decrypt

logger = logging.getLogger(__name__)


async def _resolve_entity(client, source):
    """Resolve entity using username first, then entity_id with -100 prefix."""
    if source.username:
        try:
            return await client.get_entity(source.username)
        except Exception:
            pass
    # Try with -100 prefix (channels/supergroups)
    try:
        return await client.get_entity(int(f"-100{source.tg_entity_id}"))
    except Exception:
        pass
    # Last resort: raw id
    try:
        return await client.get_entity(source.tg_entity_id)
    except Exception as e:
        logger.error("Cannot resolve entity for %s: %s", source.title, e)
        return None


async def live_search(
    keyword: str,
    source_ids: list | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit_per_source: int = 500,
) -> list[dict]:
    """Search all active sources for keyword. Returns list of result dicts."""
    async with async_session() as db:
        q = select(Source).where(Source.is_active == True)
        if source_ids:
            q = q.where(Source.id.in_(source_ids))
        sources_result = await db.execute(q)
        sources = sources_result.scalars().all()

        if not sources:
            return []

        account_ids = list(set(s.account_id for s in sources))
        acc_result = await db.execute(
            select(TgAccount).where(
                TgAccount.id.in_(account_ids),
                TgAccount.status == AccountStatus.active,
            )
        )
        accounts = {a.id: a for a in acc_result.scalars().all()}

    results = []
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)

    # Deduplicate sources by tg_entity_id
    seen_entities = set()
    unique_sources = []
    for source in sources:
        if source.tg_entity_id not in seen_entities:
            seen_entities.add(source.tg_entity_id)
            unique_sources.append(source)

    for source in unique_sources:
        account = accounts.get(source.account_id)
        if not account:
            continue

        client = None
        try:
            api_hash = decrypt(account.api_hash)
            session_str = decrypt(account.session_string)
            client = TelegramClient(StringSession(session_str), account.api_id, api_hash)
            await client.connect()

            entity = await _resolve_entity(client, source)
            if not entity:
                continue

            kwargs = {"entity": entity, "limit": limit_per_source}
            if date_to:
                dt = date_to if date_to.tzinfo else date_to.replace(tzinfo=timezone.utc)
                kwargs["offset_date"] = dt

            count = 0
            async for msg in client.iter_messages(**kwargs):
                try:
                    if not msg.text:
                        continue

                    msg_date = msg.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)

                    if date_from:
                        df = date_from if date_from.tzinfo else date_from.replace(tzinfo=timezone.utc)
                        if msg_date < df:
                            break

                    if not pattern.search(msg.text):
                        continue

                    # Get sender safely
                    sender = None
                    sender_username = None
                    sender_name = None
                    sender_phone = None
                    try:
                        sender = msg.sender
                        if sender:
                            sender_username = getattr(sender, "username", None)
                            first = getattr(sender, "first_name", "") or ""
                            last = getattr(sender, "last_name", "") or ""
                            sender_name = f"{first} {last}".strip()
                            sender_phone = getattr(sender, "phone", None)
                    except Exception:
                        pass

                    message_link = None
                    if source.username:
                        message_link = f"https://t.me/{source.username}/{msg.id}"

                    results.append({
                        "source_title": source.title,
                        "message_text": msg.text,
                        "author_username": sender_username,
                        "author_display_name": sender_name,
                        "author_phone": sender_phone,
                        "matched_keywords": [keyword],
                        "posted_at": msg_date.isoformat(),
                        "message_link": message_link,
                    })
                    count += 1

                except Exception as e:
                    logger.debug("Skipping message %s in %s: %s", msg.id, source.title, e)
                    continue

            logger.info("Source '%s': found %d matches for '%s'", source.title, count, keyword)
            await asyncio.sleep(1)

        except FloodWaitError as e:
            logger.warning("FloodWait %ds for account %s, skipping source %s", e.seconds, account.id, source.title)
        except Exception as e:
            logger.error("Error with source %s: %s", source.title, e)
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    results.sort(key=lambda r: r["posted_at"], reverse=True)
    return results
