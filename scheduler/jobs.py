"""Background scheduler for periodic price checking with queue system."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram import Bot

from config import settings
from db import crud
from scrapers.base import BaseScraper, PriceResult
from scrapers.shopee import ShopeeScraper
from scrapers.tokopedia import TokopediaScraper

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

# Scraper instances (singleton, reused across checks)
_scrapers: dict[str, BaseScraper] = {
    "tokopedia": TokopediaScraper(),
    "shopee": ShopeeScraper(),
}

# Queue lock to prevent overlap
_is_running = False


def fmt_price(price: int | None) -> str:
    """Format price as Rp string."""
    if price is None:
        return "—"
    return f"Rp{price:,.0f}".replace(",", ".")


# ---------------------------------------------------------------------------
# Public: fetch price for a single link (reusable by handlers)
# ---------------------------------------------------------------------------

async def fetch_link_price(link_id: int, url: str, platform: str,
                           selector: str | None = None) -> PriceResult:
    """Fetch the current price for a single link. Returns PriceResult."""
    scraper = _scrapers.get(platform)
    if scraper is None:
        logger.warning("No scraper for platform '%s'", platform)
        return PriceResult(price=None)
    return await scraper.fetch_price(url)


async def check_product_links(bot: Bot, product_id: int, user_id: int) -> list[dict[str, Any]]:
    """Manually check all links for a specific product.

    Returns a list of results: [{"link_id", "platform", "url", "old_price", "new_price", "source"}]
    """
    links = await crud.get_links_by_product(product_id)
    results: list[dict[str, Any]] = []

    for link in links:
        if not link.get("is_active"):
            continue

        link_id = link["id"]
        url = link["url"]
        platform = link["platform"]
        old_price = link.get("last_price")

        price_result = await fetch_link_price(link_id, url, platform, link.get("selector"))
        new_price = price_result.price

        result: dict[str, Any] = {
            "link_id": link_id,
            "platform": platform,
            "url": url,
            "old_price": old_price,
            "new_price": new_price,
            "source": price_result.source,
        }
        results.append(result)

        if new_price is not None:
            await crud.record_price(link_id, new_price, price_result.source)
            await crud.update_link_price(link_id, new_price)

        # Rate limit between links
        if len(links) > 1:
            await asyncio.sleep(settings.request_delay_seconds)

    # Evaluate alerts after all links are checked
    products = await crud.get_products_by_user(user_id)
    product_name = next((p["name"] for p in products if p["id"] == product_id), "Unknown")
    for r in results:
        if r["new_price"] is not None and r["old_price"] is not None:
            await _evaluate_alerts(
                bot, product_id, r["link_id"], r["url"], r["platform"],
                product_name, user_id, r["old_price"], r["new_price"],
            )

    return results


# ---------------------------------------------------------------------------
# Scheduler job
# ---------------------------------------------------------------------------

async def check_prices_job(bot: Bot) -> None:
    """Main scheduler job: fetch prices, evaluate alerts, send notifications.

    Uses sequential processing with rate limiting to protect VPS resources.
    """
    global _is_running

    # Overlap protection: skip if previous cycle is still running
    if _is_running:
        logger.info("Previous price check still running, skipping this cycle.")
        return

    _is_running = True
    try:
        links = await crud.get_links_due_for_check(limit=settings.max_links_per_cycle)
        if not links:
            logger.debug("No links due for check.")
            return

        logger.info("Checking prices for %d links...", len(links))

        for link_data in links:
            try:
                await _process_link(bot, link_data)
            except Exception:
                logger.exception(
                    "Error processing link #%s (%s)",
                    link_data["link_id"],
                    link_data["url"],
                )

            # Rate limiting: delay between requests
            await asyncio.sleep(settings.request_delay_seconds)

    finally:
        _is_running = False


async def _process_link(bot: Bot, link_data: dict[str, Any]) -> None:
    """Fetch price for a single link and evaluate alert rules."""
    link_id = link_data["link_id"]
    url = link_data["url"]
    platform = link_data["platform"]
    product_name = link_data["product_name"]
    user_id = link_data["user_telegram_id"]
    old_price = link_data.get("last_price")

    price_result = await fetch_link_price(link_id, url, platform, link_data.get("selector"))
    new_price = price_result.price

    if new_price is None:
        logger.warning("Failed to fetch price for link #%s (%s)", link_id, url)
        # Still update last_checked to avoid retrying repeatedly
        await crud.update_link_price(link_id, old_price or 0)
        return

    # Record price & update link cache
    await crud.record_price(link_id, new_price, price_result.source)
    await crud.update_link_price(link_id, new_price)

    logger.info(
        "Link #%s (%s) [%s]: %s → %s",
        link_id,
        platform,
        price_result.source,
        fmt_price(old_price) if old_price else "N/A",
        fmt_price(new_price),
    )

    # Skip alert evaluation on first fetch (no old price to compare)
    if old_price is None:
        return

    await _evaluate_alerts(bot, link_data["product_id"], link_id, url,
                           platform, product_name, user_id, old_price, new_price)


# ---------------------------------------------------------------------------
# Alert evaluation (shared)
# ---------------------------------------------------------------------------

async def _evaluate_alerts(
    bot: Bot, product_id: int, link_id: int, url: str,
    platform: str, product_name: str, user_id: int,
    old_price: int, new_price: int,
) -> None:
    """Evaluate all alert rules for a link and send notifications."""
    alerts = await crud.get_alerts_by_product(product_id)
    for alert in alerts:
        should_notify = False
        alert_text = ""

        rule_type = alert["rule_type"]

        if rule_type == "PRICE_DROP" and new_price < old_price:
            diff = old_price - new_price
            pct = (diff / old_price) * 100
            should_notify = True
            alert_text = (
                f"🚨 <b>HARGA TURUN!</b> 🚨\n\n"
                f"📦 <b>{product_name}</b> di {platform.title()}\n"
                f"💰 Harga lama: {fmt_price(old_price)}\n"
                f"💰 Harga baru: <b>{fmt_price(new_price)}</b>\n"
                f"📉 Turun: {fmt_price(diff)} (-{pct:.1f}%)\n\n"
                f"🔗 <a href=\"{url}\">Beli Sekarang</a>"
            )

        elif rule_type == "TARGET_PRICE" and alert.get("target_value"):
            target = alert["target_value"]
            if new_price <= target:
                should_notify = True
                alert_text = (
                    f"🎯 <b>TARGET HARGA TERCAPAI!</b> 🎯\n\n"
                    f"📦 <b>{product_name}</b> di {platform.title()}\n"
                    f"💰 Harga saat ini: <b>{fmt_price(new_price)}</b>\n"
                    f"🎯 Target Anda: {fmt_price(target)}\n\n"
                    f"🔗 <a href=\"{url}\">Beli Sekarang</a>"
                )

        elif rule_type == "HISTORICAL_LOW":
            lowest = await crud.get_lowest_price(link_id)
            if lowest is not None and new_price <= lowest:
                should_notify = True
                alert_text = (
                    f"📉 <b>REKOR HARGA TERENDAH!</b> 📉\n\n"
                    f"📦 <b>{product_name}</b> di {platform.title()}\n"
                    f"💰 Harga saat ini: <b>{fmt_price(new_price)}</b>\n"
                    f"📊 Rekor sebelumnya: {fmt_price(lowest)}\n\n"
                    f"🔗 <a href=\"{url}\">Beli Sekarang</a>"
                )

        if should_notify and alert_text:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=alert_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                logger.info("Alert sent to user %s for %s", user_id, product_name)
            except Exception:
                logger.exception("Failed to send alert to user %s", user_id)
