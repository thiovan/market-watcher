"""/list command handler — view and manage watchlist."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards.inline import watchlist_item_keyboard
from bot.handlers.check_history import _format_local_time
from db import crud

logger = logging.getLogger(__name__)

router = Router(name="watchlist")


def _fmt_price(price: int | None) -> str:
    """Format price as Rp string or dash."""
    if price is None:
        return "—"
    return f"Rp{price:,.0f}".replace(",", ".")


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    """Show all watched products for the user."""
    user_id = message.from_user.id  # type: ignore[union-attr]
    products = await crud.get_products_by_user(user_id)

    if not products:
        await message.answer(
            "📭 <b>Watchlist kosong.</b>\n\n"
            "Gunakan /add untuk menambah produk pertama.",
            parse_mode="HTML",
        )
        return

    for idx, product in enumerate(products, 1):
        links = await crud.get_links_by_product(product["id"])
        prices_parts: list[str] = []
        for link in links:
            platform = link["platform"].title()
            price_str = _fmt_price(link.get("last_price"))
            prices_parts.append(f"  • {platform}: {price_str}")

        prices_text = "\n".join(prices_parts) if prices_parts else "  <i>Belum ada data harga</i>"
        interval = product.get("check_interval_minutes", 240)

        # Calculate next check time
        oldest_check = None
        for link in links:
            ts_str = link.get("last_checked")
            if ts_str:
                try:
                    if "T" not in ts_str:
                        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    else:
                        dt = datetime.fromisoformat(ts_str)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                    if oldest_check is None or dt < oldest_check:
                        oldest_check = dt
                except Exception:
                    pass

        next_str = "<i>Menunggu pengecekan pertama...</i>"
        if oldest_check is not None:
            next_dt = oldest_check + timedelta(minutes=interval)
            now = datetime.now(timezone.utc)
            if next_dt <= now:
                next_str = "<b>Segera</b> (dalam antrean)"
            else:
                next_str = next_dt.astimezone().strftime("%Y-%m-%d %H:%M")

        text = (
            f"<b>{idx}. {product['name']}</b>\n"
            f"{prices_text}\n"
            f"⏱️ Cek setiap: {_fmt_interval(interval)}\n"
            f"⏳ Pengecekan selanjutnya: {next_str}"
        )

        await message.answer(
            text,
            reply_markup=watchlist_item_keyboard(product["id"]),
            parse_mode="HTML",
        )


def _fmt_interval(minutes: int) -> str:
    """Format interval in human-readable form."""
    if minutes < 60:
        return f"{minutes} menit"
    hours = minutes / 60
    if hours == int(hours):
        return f"{int(hours)} jam"
    return f"{hours:.1f} jam"
