"""Bot initialisation, dispatcher setup, and lifecycle management."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.handlers import add, callbacks, check_history, cookies, settings, start, watchlist
from bot.middleware import AdminOnlyMiddleware
from config import settings as app_settings
from db.database import close_db, init_db
from scheduler.jobs import check_prices_job

logger = logging.getLogger(__name__)

# Scheduler instance (module-level so handlers can reference it if needed)
scheduler = AsyncIOScheduler()


async def on_startup(bot: Bot) -> None:
    """Run once when the bot starts polling."""
    logger.info("Initialising database...")
    await init_db()

    logger.info(
        "Starting scheduler (interval: %d min)...",
        app_settings.check_interval_minutes,
    )
    scheduler.add_job(
        check_prices_job,
        "interval",
        minutes=app_settings.check_interval_minutes,
        args=[bot],
        id="price_checker",
        replace_existing=True,
        max_instances=1,
    )
    # Also run once immediately on startup
    scheduler.add_job(
        check_prices_job,
        "date",  # run once now
        args=[bot],
        id="price_checker_initial",
    )
    scheduler.start()

    me = await bot.get_me()
    logger.info("Bot started: @%s", me.username)


async def on_shutdown(bot: Bot) -> None:
    """Run once when the bot stops."""
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=False)

    logger.info("Closing browser...")
    from scrapers.browser import close_browser
    await close_browser()

    logger.info("Closing database...")
    await close_db()
    logger.info("Bot stopped.")


def create_dispatcher() -> Dispatcher:
    """Build and configure the Dispatcher with all routers."""
    dp = Dispatcher(storage=MemoryStorage())

    # Security: admin-only access
    dp.message.middleware(AdminOnlyMiddleware())
    dp.callback_query.middleware(AdminOnlyMiddleware())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(add.router)
    dp.include_router(watchlist.router)
    dp.include_router(check_history.router)
    dp.include_router(cookies.router)
    dp.include_router(settings.router)
    dp.include_router(callbacks.router)

    # Lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return dp
