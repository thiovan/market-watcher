"""Async SQLite database connection and initialisation."""

from __future__ import annotations

import logging

import aiosqlite

from config import settings
from db.models import SCHEMA_SQL

_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    """Create tables if they don't exist and store the connection."""
    global _db
    db_path = settings.db_path
    _db = await aiosqlite.connect(str(db_path))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    await _db.executescript(SCHEMA_SQL)
    await _db.commit()

    # Migration: add 'source' column to price_history if missing
    try:
        cursor = await _db.execute("PRAGMA table_info(price_history)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "source" not in columns:
            await _db.execute(
                "ALTER TABLE price_history ADD COLUMN source TEXT NOT NULL DEFAULT 'no_cookies'"
            )
            await _db.commit()
            logging.getLogger(__name__).info("Migrated: added 'source' column to price_history")
    except Exception:
        pass


async def get_db() -> aiosqlite.Connection:
    """Return the active database connection, initialising if needed."""
    global _db
    if _db is None:
        await init_db()
    assert _db is not None
    return _db


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
