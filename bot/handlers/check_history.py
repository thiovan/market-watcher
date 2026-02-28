"""/check and /history command handlers."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import crud
from scheduler.jobs import check_product_links, fmt_price

logger = logging.getLogger(__name__)

router = Router(name="check_history")


# ---------------------------------------------------------------------------
# /check — Manual price check
# ---------------------------------------------------------------------------

@router.message(Command("check"))
async def cmd_check(message: Message) -> None:
    """Manually trigger a price check for all products or a specific one.

    Usage:
        /check         — Check all products
        /check <id>    — Check a specific product
    """
    user_id = message.from_user.id  # type: ignore[union-attr]
    parts = (message.text or "").split()

    products = await crud.get_products_by_user(user_id)
    if not products:
        await message.answer("📭 Watchlist kosong. Gunakan /add terlebih dahulu.")
        return

    # Specific product
    if len(parts) > 1:
        try:
            product_id = int(parts[1])
        except ValueError:
            await message.answer("❌ ID produk harus berupa angka.\nFormat: <code>/check [id]</code>", parse_mode="HTML")
            return

        product = next((p for p in products if p["id"] == product_id), None)
        if product is None:
            await message.answer("❌ Produk tidak ditemukan.")
            return

        await _check_single_product(message, product)
        return

    # All products
    await message.answer(f"🔄 Mengecek harga {len(products)} produk...")
    for product in products:
        await _check_single_product(message, product)


async def _check_single_product(message: Message, product: dict) -> None:
    """Check prices for a single product and report results."""
    from aiogram import Bot

    bot: Bot = message.bot  # type: ignore[assignment]
    user_id = message.from_user.id  # type: ignore[union-attr]
    product_id = product["id"]
    name = product["name"]

    status_msg = await message.answer(f"🔍 Mengecek <b>{name}</b>...", parse_mode="HTML")

    results = await check_product_links(bot, product_id, user_id)

    if not results:
        await status_msg.edit_text(f"⚠️ <b>{name}</b> — Tidak ada link aktif.", parse_mode="HTML")
        return

    parts: list[str] = [f"📦 <b>{name}</b>\n"]
    for r in results:
        platform = r["platform"].title()
        old = r["old_price"]
        new = r["new_price"]
        source_icon = "🍪" if r.get("source") == "cookies" else "🌐"

        if new is None:
            parts.append(f"  ❌ {platform}: Gagal mengambil harga")
        elif old is None:
            parts.append(f"  🆕 {platform}: {fmt_price(new)} {source_icon} (harga awal)")
        elif new < old:
            diff = old - new
            pct = (diff / old) * 100
            parts.append(f"  📉 {platform}: {fmt_price(old)} → <b>{fmt_price(new)}</b> {source_icon} (-{pct:.1f}%)")
        elif new > old:
            diff = new - old
            pct = (diff / old) * 100
            parts.append(f"  📈 {platform}: {fmt_price(old)} → {fmt_price(new)} {source_icon} (+{pct:.1f}%)")
        else:
            parts.append(f"  ➡️ {platform}: {fmt_price(new)} {source_icon} (tidak berubah)")

    try:
        await status_msg.edit_text("\n".join(parts), parse_mode="HTML")
    except Exception:
        await message.answer("\n".join(parts), parse_mode="HTML")


# ---------------------------------------------------------------------------
# /history — View price change history
# ---------------------------------------------------------------------------

@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    """Show price history for a product.

    Usage:
        /history         — Show product list to choose
        /history <id>    — Show history for a specific product
    """
    user_id = message.from_user.id  # type: ignore[union-attr]
    parts = (message.text or "").split()

    products = await crud.get_products_by_user(user_id)
    if not products:
        await message.answer("📭 Watchlist kosong. Gunakan /add terlebih dahulu.")
        return

    # If no ID specified, list products with IDs
    if len(parts) < 2:
        lines = ["📊 <b>Pilih produk untuk melihat riwayat harga:</b>\n"]
        for p in products:
            lines.append(f"  • <code>/history {p['id']}</code> — {p['name']}")
        await message.answer("\n".join(lines), parse_mode="HTML")
        return

    try:
        product_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID produk harus berupa angka.\nFormat: <code>/history [id]</code>", parse_mode="HTML")
        return

    product = next((p for p in products if p["id"] == product_id), None)
    if product is None:
        await message.answer("❌ Produk tidak ditemukan.")
        return

    links = await crud.get_links_by_product(product_id)
    if not links:
        await message.answer(f"⚠️ <b>{product['name']}</b> — Tidak ada link.", parse_mode="HTML")
        return

    all_parts: list[str] = [f"📊 <b>Riwayat Harga — {product['name']}</b>\n"]

    for link in links:
        platform = link["platform"].title()
        history = await crud.get_price_history(link["id"], limit=15)
        lowest = await crud.get_lowest_price(link["id"])

        all_parts.append(f"\n🔗 <b>{platform}</b> (link #{link['id']})")
        all_parts.append(f"  📉 Terendah: {fmt_price(lowest)}")

        if not history:
            all_parts.append("  <i>Belum ada riwayat</i>")
            continue

        all_parts.append("  📈 Riwayat perubahan:")

        prev_price = None
        for i, h in enumerate(reversed(history)):  # oldest first
            price = h["price"]
            ts = h["checked_at"][:16].replace("T", " ")
            source = h.get("source", "no_cookies")
            src_icon = "🍪" if source == "cookies" else "🌐"

            if prev_price is None:
                indicator = "🆕"
                change_str = ""
            elif price < prev_price:
                diff = prev_price - price
                pct = (diff / prev_price) * 100
                indicator = "📉"
                change_str = f" <i>(-{pct:.1f}%)</i>"
            elif price > prev_price:
                diff = price - prev_price
                pct = (diff / prev_price) * 100
                indicator = "📈"
                change_str = f" <i>(+{pct:.1f}%)</i>"
            else:
                indicator = "➡️"
                change_str = ""

            all_parts.append(f"    {indicator} {fmt_price(price)}{change_str} {src_icon} — {ts}")
            prev_price = price

    all_parts.append("\n<i>🍪 = cookies, 🌐 = tanpa cookies</i>")
    await message.answer("\n".join(all_parts), parse_mode="HTML")
