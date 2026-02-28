"""Callback query handlers for inline keyboard buttons."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards.inline import confirm_delete_keyboard, interval_keyboard
from db import crud

logger = logging.getLogger(__name__)

router = Router(name="callbacks")


def _fmt_price(price: int | None) -> str:
    if price is None:
        return "—"
    return f"Rp{price:,.0f}".replace(",", ".")


# ---------------------------------------------------------------------------
# Product detail
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("detail:"))
async def cb_detail(callback: CallbackQuery) -> None:
    """Show detailed info for a product."""
    product_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await callback.answer()

    links = await crud.get_links_by_product(product_id)
    alerts = await crud.get_alerts_by_product(product_id)

    parts: list[str] = ["📊 <b>Detail Produk</b>\n"]

    for link in links:
        platform = link["platform"].title()
        price_str = _fmt_price(link.get("last_price"))
        lowest = await crud.get_lowest_price(link["id"])
        lowest_str = _fmt_price(lowest)
        history = await crud.get_price_history(link["id"], limit=5)

        parts.append(
            f"\n🔗 <b>{platform}</b> (link #{link['id']})\n"
            f"  Harga terakhir: {price_str}\n"
            f"  Harga terendah: {lowest_str}\n"
            f"  URL: {link['url']}"
        )

        if history:
            parts.append("  📈 Riwayat terbaru:")
            for h in history[:5]:
                parts.append(f"    • {_fmt_price(h['price'])} ({h['checked_at'][:16]})")

    if alerts:
        labels = {
            "PRICE_DROP": "🔻 Harga Turun",
            "TARGET_PRICE": "🎯 Target Harga",
            "HISTORICAL_LOW": "📉 Rekor Termurah",
        }
        parts.append("\n🔔 <b>Alert Rules:</b>")
        for a in alerts:
            label = labels.get(a["rule_type"], a["rule_type"])
            val = f" (Rp{a['target_value']:,.0f})" if a.get("target_value") else ""
            parts.append(f"  • {label}{val}")

    await callback.message.answer("\n".join(parts), parse_mode="HTML")  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Interval
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("interval:"))
async def cb_interval(callback: CallbackQuery) -> None:
    """Show interval selection keyboard."""
    product_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await callback.answer()
    await callback.message.answer(  # type: ignore[union-attr]
        "⏱️ Pilih interval pengecekan harga:",
        reply_markup=interval_keyboard(product_id),
    )


@router.callback_query(F.data.startswith("set_interval:"))
async def cb_set_interval(callback: CallbackQuery) -> None:
    """Apply the selected interval."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    product_id = int(parts[1])
    interval = int(parts[2])
    await callback.answer()

    await crud.update_product_interval(product_id, interval)
    await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]

    hours = interval / 60
    label = f"{interval} menit" if interval < 60 else f"{hours:.0f} jam"
    await callback.message.answer(  # type: ignore[union-attr]
        f"✅ Interval diubah menjadi <b>{label}</b>.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("delete:"))
async def cb_delete(callback: CallbackQuery) -> None:
    """Ask for delete confirmation."""
    product_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await callback.answer()
    await callback.message.answer(  # type: ignore[union-attr]
        "⚠️ Yakin ingin menghapus produk ini beserta semua riwayat harganya?",
        reply_markup=confirm_delete_keyboard(product_id),
    )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def cb_confirm_delete(callback: CallbackQuery) -> None:
    """Delete the product."""
    product_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await callback.answer()

    try:
        await crud.delete_product(product_id)
        await callback.message.edit_text("🗑️ Produk berhasil dihapus.")  # type: ignore[union-attr]
    except Exception:
        logger.exception("Failed to delete product %s", product_id)
        await callback.message.edit_text("❌ Gagal menghapus produk.")  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# History (inline button)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("history:"))
async def cb_history(callback: CallbackQuery) -> None:
    """Show price history for a product via inline button."""
    product_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await callback.answer()

    links = await crud.get_links_by_product(product_id)
    if not links:
        await callback.message.answer("⚠️ Tidak ada link untuk produk ini.")  # type: ignore[union-attr]
        return

    all_parts: list[str] = ["📊 <b>Riwayat Harga</b>\n"]

    for link in links:
        platform = link["platform"].title()
        history = await crud.get_price_history(link["id"], limit=10)
        lowest = await crud.get_lowest_price(link["id"])

        all_parts.append(f"\n🔗 <b>{platform}</b>")
        all_parts.append(f"  📉 Terendah: {_fmt_price(lowest)}")

        if not history:
            all_parts.append("  <i>Belum ada riwayat</i>")
            continue

        prev_price = None
        for h in reversed(history):
            price = h["price"]
            ts = h["checked_at"][:16].replace("T", " ")

            if prev_price is None:
                indicator = "🆕"
                change = ""
            elif price < prev_price:
                pct = ((prev_price - price) / prev_price) * 100
                indicator = "📉"
                change = f" <i>(-{pct:.1f}%)</i>"
            elif price > prev_price:
                pct = ((price - prev_price) / prev_price) * 100
                indicator = "📈"
                change = f" <i>(+{pct:.1f}%)</i>"
            else:
                indicator = "➡️"
                change = ""

            all_parts.append(f"    {indicator} {_fmt_price(price)}{change} — {ts}")
            prev_price = price

    await callback.message.answer("\n".join(all_parts), parse_mode="HTML")  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Check price (inline button)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("check:"))
async def cb_check(callback: CallbackQuery) -> None:
    """Manually trigger price check via inline button."""
    from scheduler.jobs import check_product_links, fmt_price as _fp

    product_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    user_id = callback.from_user.id
    await callback.answer("🔄 Mengecek harga...")

    products = await crud.get_products_by_user(user_id)
    product = next((p for p in products if p["id"] == product_id), None)
    if product is None:
        await callback.message.answer("❌ Produk tidak ditemukan.")  # type: ignore[union-attr]
        return

    name = product["name"]
    status_msg = await callback.message.answer(f"🔍 Mengecek <b>{name}</b>...", parse_mode="HTML")  # type: ignore[union-attr]

    from aiogram import Bot
    bot: Bot = callback.bot  # type: ignore[assignment]
    results = await check_product_links(bot, product_id, user_id)

    parts: list[str] = [f"📦 <b>{name}</b>\n"]
    for r in results:
        platform = r["platform"].title()
        old = r["old_price"]
        new = r["new_price"]
        if new is None:
            parts.append(f"  ❌ {platform}: Gagal")
        elif old is None:
            parts.append(f"  🆕 {platform}: {_fp(new)}")
        elif new < old:
            pct = ((old - new) / old) * 100
            parts.append(f"  📉 {platform}: {_fp(old)} → <b>{_fp(new)}</b> (-{pct:.1f}%)")
        elif new > old:
            pct = ((new - old) / old) * 100
            parts.append(f"  📈 {platform}: {_fp(old)} → {_fp(new)} (+{pct:.1f}%)")
        else:
            parts.append(f"  ➡️ {platform}: {_fp(new)} (tidak berubah)")

    try:
        await status_msg.edit_text("\n".join(parts), parse_mode="HTML")
    except Exception:
        await callback.message.answer("\n".join(parts), parse_mode="HTML")  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery) -> None:
    """Cancel any inline action."""
    await callback.answer("Dibatalkan.")
    await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
