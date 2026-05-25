"""Telegram parser worker process.

Runs as a separate process (see Procfile).
Uses APScheduler to periodically parse active sources.
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    logger.info("Worker started (placeholder — Telethon integration in Stage 4)")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
