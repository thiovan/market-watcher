"""Market Watcher Bot — entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from bot.main import create_dispatcher
from config import settings


def setup_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Reduce noise from libraries and hide token traces
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def main() -> None:
    """Start the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        settings.validate()
    except ValueError as exc:
        logger.critical("Configuration error: %s", exc)
        sys.exit(1)

    logger.info("Starting Market Watcher Bot...")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode="HTML",
            link_preview_is_disabled=True,
        ),
    )
    dp = create_dispatcher()

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
