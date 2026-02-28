"""CRUD operations for all database tables."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiosqlite

from db.database import get_db


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

async def add_product(name: str, user_id: int, interval: int = 240) -> int:
    """Insert a product and return its id."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO products (name, user_telegram_id, check_interval_minutes) VALUES (?, ?, ?)",
        (name, user_id, interval),
    )
    await db.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


async def get_products_by_user(user_id: int) -> list[dict[str, Any]]:
    """Return all products for a Telegram user."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM products WHERE user_telegram_id = ? ORDER BY id", (user_id,)
    )
    return [dict(r) for r in rows]


async def delete_product(product_id: int) -> None:
    """Delete a product and its cascaded children."""
    db = await get_db()
    await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    await db.commit()


async def update_product_interval(product_id: int, interval: int) -> None:
    """Update the check interval for a product."""
    db = await get_db()
    await db.execute(
        "UPDATE products SET check_interval_minutes = ? WHERE id = ?",
        (interval, product_id),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Product Links
# ---------------------------------------------------------------------------

async def add_product_link(
    product_id: int,
    url: str,
    platform: str = "unknown",
    selector: str | None = None,
) -> int:
    """Insert a product link and return its id."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO product_links (product_id, url, platform, selector) VALUES (?, ?, ?, ?)",
        (product_id, url, platform, selector),
    )
    await db.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


async def get_links_by_product(product_id: int) -> list[dict[str, Any]]:
    """Return all links for a product."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM product_links WHERE product_id = ? ORDER BY id",
        (product_id,),
    )
    return [dict(r) for r in rows]


async def update_link_selector(link_id: int, selector: str) -> None:
    """Update the CSS/XPath selector for a link."""
    db = await get_db()
    await db.execute(
        "UPDATE product_links SET selector = ? WHERE id = ?", (selector, link_id)
    )
    await db.commit()


async def toggle_link_active(link_id: int, is_active: bool) -> None:
    """Enable or disable a link."""
    db = await get_db()
    await db.execute(
        "UPDATE product_links SET is_active = ? WHERE id = ?",
        (int(is_active), link_id),
    )
    await db.commit()


async def update_link_price(link_id: int, price: int) -> None:
    """Update the cached last_price and last_checked timestamp on a link."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE product_links SET last_price = ?, last_checked = ? WHERE id = ?",
        (price, now, link_id),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Price History
# ---------------------------------------------------------------------------

async def record_price(link_id: int, price: int, source: str = "no_cookies") -> int:
    """Record a price snapshot and return its id."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO price_history (link_id, price, source) VALUES (?, ?, ?)",
        (link_id, price, source),
    )
    await db.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


async def get_price_history(link_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent price history for a link (newest first)."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM price_history WHERE link_id = ? ORDER BY checked_at DESC LIMIT ?",
        (link_id, limit),
    )
    return [dict(r) for r in rows]


async def get_lowest_price(link_id: int) -> int | None:
    """Return the historical lowest price for a link, or None."""
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT MIN(price) AS min_price FROM price_history WHERE link_id = ?",
        (link_id,),
    )
    if row and row[0]["min_price"] is not None:
        return int(row[0]["min_price"])
    return None


async def get_last_price(link_id: int) -> int | None:
    """Return the most recently recorded price for a link."""
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT price FROM price_history WHERE link_id = ? ORDER BY id DESC LIMIT 1",
        (link_id,),
    )
    if row:
        return int(row[0]["price"])
    return None


# ---------------------------------------------------------------------------
# Alert Rules
# ---------------------------------------------------------------------------

async def add_alert_rule(
    product_id: int, rule_type: str, target_value: int | None = None
) -> int:
    """Insert an alert rule and return its id."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO alert_rules (product_id, rule_type, target_value) VALUES (?, ?, ?)",
        (product_id, rule_type, target_value),
    )
    await db.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


async def get_alerts_by_product(product_id: int) -> list[dict[str, Any]]:
    """Return all alert rules for a product."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM alert_rules WHERE product_id = ? ORDER BY id",
        (product_id,),
    )
    return [dict(r) for r in rows]


async def delete_alert_rule(rule_id: int) -> None:
    """Delete an alert rule by id."""
    db = await get_db()
    await db.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
    await db.commit()


# ---------------------------------------------------------------------------
# Scheduler queries
# ---------------------------------------------------------------------------

async def get_links_due_for_check(limit: int = 20) -> list[dict[str, Any]]:
    """Return active links whose check interval has elapsed, oldest first.

    Also returns product info (name, user_telegram_id) via JOIN.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        """
        SELECT
            pl.id           AS link_id,
            pl.product_id,
            pl.url,
            pl.platform,
            pl.selector,
            pl.last_price,
            p.name          AS product_name,
            p.user_telegram_id,
            p.check_interval_minutes
        FROM product_links pl
        JOIN products p ON p.id = pl.product_id
        WHERE pl.is_active = 1
          AND (
              pl.last_checked IS NULL
              OR datetime(pl.last_checked, '+' || p.check_interval_minutes || ' minutes') <= datetime('now')
          )
        ORDER BY pl.last_checked ASC NULLS FIRST
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in rows]
