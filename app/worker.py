"""Telegram parser worker process.

Runs as a separate process (see Procfile).
Uses APScheduler to periodically parse active sources via Telethon.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.errors import AuthKeyError, FloodWaitError
from telethon.sessions import StringSession

from app.config import settings
from app.database import async_session
from app.models.agent import Agent
from app.models.agent_result import AgentResult
from app.models.filter_set import FilterSet
from app.models.job import Job, JobStatus, JobType
from app.models.keyword import Keyword
from app.models.match import Match
from app.models.notification import Notification
from app.models.source import Source
from app.models.tg_account import AccountStatus, TgAccount
from app.services.encryption import decrypt
from app.services.live_parser import live_search
from app.services.matcher import match_message
from app.services.query_processor import process_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_DELAY = 2


async def _get_client(account: TgAccount) -> TelegramClient:
    api_hash = decrypt(account.api_hash)
    session_str = decrypt(account.session_string)
    client = TelegramClient(StringSession(session_str), account.api_id, api_hash)
    await client.connect()
    return client


async def _load_active_filters(db: AsyncSession) -> list[dict]:
    """Load all active filter sets with their keywords."""
    result = await db.execute(
        select(FilterSet).where(FilterSet.is_active == True)
    )
    filter_sets = result.scalars().all()

    filters = []
    for fs in filter_sets:
        kw_result = await db.execute(
            select(Keyword).where(Keyword.filter_set_id == fs.id)
        )
        keywords = [
            {
                "pattern": kw.pattern,
                "match_type": kw.match_type,
                "is_case_sensitive": kw.is_case_sensitive,
            }
            for kw in kw_result.scalars().all()
        ]
        if keywords:
            filters.append({
                "filter_set_id": fs.id,
                "source_ids": fs.source_ids or [],
                "date_from": fs.date_from,
                "date_to": fs.date_to,
                "keywords": keywords,
            })
    return filters


async def _save_match(
    db: AsyncSession,
    source: Source,
    filter_set_id: uuid.UUID | None,
    msg,
    matched_keywords: list[str],
):
    """Save a match record, skip duplicates."""
    username = source.username
    message_link = None
    if username:
        message_link = f"https://t.me/{username}/{msg.id}"

    sender = await msg.get_sender() if msg.sender_id else None
    match = Match(
        source_id=source.id,
        filter_set_id=filter_set_id,
        message_id=msg.id,
        message_link=message_link,
        message_text=msg.text or "",
        matched_keywords=matched_keywords,
        author_user_id=msg.sender_id,
        author_username=getattr(sender, "username", None) if sender else None,
        author_display_name=(
            f"{getattr(sender, 'first_name', '') or ''} {getattr(sender, 'last_name', '') or ''}".strip()
            if sender else None
        ),
        author_phone=getattr(sender, "phone", None) if sender else None,
        source_title=source.title,
        posted_at=msg.date,
    )
    db.add(match)
    try:
        await db.flush()
    except Exception:
        await db.rollback()


async def parse_source(source_id: uuid.UUID, is_first_pass: bool = False):
    """Parse a single source for new messages."""
    async with async_session() as db:
        result = await db.execute(
            select(Source).where(Source.id == source_id)
        )
        source = result.scalar_one_or_none()
        if not source or not source.is_active:
            return

        result = await db.execute(
            select(TgAccount).where(TgAccount.id == source.account_id)
        )
        account = result.scalar_one_or_none()
        if not account or account.status != AccountStatus.active:
            return

        filters = await _load_active_filters(db)
        relevant_filters = [
            f for f in filters
            if not f["source_ids"] or source.id in f["source_ids"]
        ]

        try:
            client = await _get_client(account)
        except Exception as e:
            logger.error("Failed to connect account %s: %s", account.id, e)
            account.status = AccountStatus.error
            account.last_error = str(e)
            await db.commit()
            return

        try:
            # Resolve by username first, then -100 prefix, then raw id
            entity = None
            if source.username:
                try:
                    entity = await client.get_entity(source.username)
                except Exception:
                    pass
            if not entity:
                try:
                    entity = await client.get_entity(int(f"-100{source.tg_entity_id}"))
                except Exception:
                    pass
            if not entity:
                entity = await client.get_entity(source.tg_entity_id)

            kwargs = {"entity": entity, "limit": 100}
            if not is_first_pass and source.last_parsed_message_id:
                kwargs["min_id"] = source.last_parsed_message_id

            if is_first_pass and source.first_pass_until:
                kwargs["offset_date"] = None

            max_msg_id = source.last_parsed_message_id or 0
            count = 0

            async for msg in client.iter_messages(**kwargs):
                if not msg.text:
                    continue

                if is_first_pass and source.first_pass_until:
                    if msg.date.replace(tzinfo=timezone.utc) < source.first_pass_until.replace(tzinfo=timezone.utc):
                        break

                for f in relevant_filters:
                    matched = match_message(
                        msg.text,
                        msg.date,
                        f["keywords"],
                        f.get("date_from"),
                        f.get("date_to"),
                    )
                    if matched:
                        await _save_match(db, source, f["filter_set_id"], msg, matched)

                if msg.id > max_msg_id:
                    max_msg_id = msg.id
                count += 1

                if count % 100 == 0:
                    await asyncio.sleep(BATCH_DELAY)

            source.last_parsed_message_id = max_msg_id
            if is_first_pass:
                source.first_pass_done = True
            await db.commit()
            logger.info("Parsed %d messages from %s", count, source.title)

        except FloodWaitError as e:
            logger.warning("FloodWait %d sec for account %s", e.seconds, account.id)
            account.status = AccountStatus.flood_wait
            account.last_error = f"FloodWait {e.seconds}s"
            await db.commit()
            await asyncio.sleep(e.seconds)
            account.status = AccountStatus.active
            account.last_error = None
            await db.commit()

        except (AuthKeyError, Exception) as e:
            if isinstance(e, AuthKeyError):
                logger.error("AuthKeyError for account %s", account.id)
                account.status = AccountStatus.banned
            else:
                logger.error("Error parsing %s: %s", source.title, e)
                account.status = AccountStatus.error
            account.last_error = str(e)
            await db.commit()

        finally:
            await client.disconnect()


async def process_jobs():
    """Pick up queued jobs and execute them."""
    async with async_session() as db:
        result = await db.execute(
            select(Job)
            .where(Job.status == JobStatus.queued)
            .order_by(Job.created_at)
            .limit(5)
        )
        jobs = result.scalars().all()

        for job in jobs:
            job.status = JobStatus.running
            await db.commit()

            try:
                if job.type == JobType.first_pass:
                    source_id = uuid.UUID(job.payload["source_id"])
                    await parse_source(source_id, is_first_pass=True)
                elif job.type == JobType.parse_source:
                    source_id = uuid.UUID(job.payload["source_id"])
                    await parse_source(source_id)
                elif job.type == JobType.agent_monitor:
                    await _process_agent_job(db, job)
                job.status = JobStatus.done
            except Exception as e:
                logger.error("Job %s failed: %s", job.id, e)
                job.status = JobStatus.failed
                job.error = str(e)
            await db.commit()


async def scheduled_parse():
    """Periodic task: parse all active sources."""
    async with async_session() as db:
        result = await db.execute(
            select(Source).where(
                Source.is_active == True,
                Source.first_pass_done == True,
            )
        )
        sources = result.scalars().all()

    for source in sources:
        await parse_source(source.id)
        await asyncio.sleep(BATCH_DELAY)


async def _process_agent_job(db: AsyncSession, job: Job):
    """Process agent monitoring job."""
    agent_id = uuid.UUID(job.payload['agent_id'])
    keywords = job.payload['keywords']
    source_ids = job.payload.get('source_ids', [])
    collection_ids = job.payload.get('collection_ids', [])
    mode = job.payload['search_mode']

    # Convert source_ids strings to UUIDs
    source_uuids = [uuid.UUID(s) if isinstance(s, str) else s for s in source_ids]

    # Search all keywords, collect matches
    all_matches = []
    for keyword in keywords:
        try:
            # Expand query based on mode
            expanded_terms = await process_query(keyword, mode)

            # Search with expanded terms
            matches = await live_search(
                keyword=keyword,
                source_ids=source_uuids if source_uuids else None,
                expanded_terms=expanded_terms,
            )
            all_matches.extend(matches)
        except Exception as e:
            logger.error(f"Agent {agent_id} keyword {keyword} failed: {e}")
            continue

    # Save results
    result = AgentResult(
        agent_id=agent_id,
        found_count=len(all_matches),
        matches=all_matches
    )
    db.add(result)
    await db.flush()  # Get result.id

    # Create notification if matches found
    agent = await db.get(Agent, agent_id)
    if agent and all_matches:
        notification = Notification(
            user_id=agent.user_id,
            type='agent_found',
            agent_id=agent_id,
            agent_result_id=result.id,
            title=f"Agent '{agent.name}' found {len(all_matches)} matches"
        )
        db.add(notification)

    # Update agent stats
    if agent:
        agent.last_run_at = datetime.now(timezone.utc)
        agent.results_count += len(all_matches)

    logger.info(f"Agent {agent_id} completed: {len(all_matches)} matches")


async def check_active_agents():
    """Check all active agents and create jobs (hourly 8-20)."""
    async with async_session() as db:
        result = await db.execute(
            select(Agent).where(Agent.is_active == True)
        )
        agents = result.scalars().all()

        for agent in agents:
            job = Job(
                type=JobType.agent_monitor,
                payload={
                    'agent_id': str(agent.id),
                    'keywords': agent.keywords,
                    'source_ids': agent.source_ids,
                    'collection_ids': agent.collection_ids,
                    'search_mode': agent.search_mode,
                },
                status=JobStatus.queued
            )
            db.add(job)

        if agents:
            await db.commit()
            logger.info("Created %d agent monitor jobs", len(agents))


async def main():
    logger.info("Worker starting, parse interval: %d min", settings.PARSE_INTERVAL_MINUTES)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_parse,
        "interval",
        minutes=settings.PARSE_INTERVAL_MINUTES,
        id="scheduled_parse",
    )
    scheduler.add_job(
        process_jobs,
        "interval",
        seconds=15,
        id="process_jobs",
    )
    scheduler.add_job(
        check_active_agents,
        "cron",
        hour="8-20",
        minute="0",
        id="check_active_agents",
    )
    scheduler.start()

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
