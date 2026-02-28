"""/settings and /update_selector command handlers."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import crud

logger = logging.getLogger(__name__)

router = Router(name="settings")


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    """Show current settings summary."""
    user_id = message.from_user.id  # type: ignore[union-attr]
    products = await crud.get_products_by_user(user_id)

    if not products:
        await message.answer(
            "⚙️ Belum ada produk. Gunakan /add terlebih dahulu.",
            parse_mode="HTML",
        )
        return

    lines = ["⚙️ <b>Pengaturan Saat Ini</b>\n"]
    for p in products:
        interval = p.get("check_interval_minutes", 240)
        lines.append(f"• <b>{p['name']}</b> — cek setiap {interval} menit")

    lines.append(
        "\n<i>Untuk mengubah interval, kirim /list lalu klik tombol ⏱️ Interval.</i>"
    )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("update_selector"))
async def cmd_update_selector(message: Message) -> None:
    """Update CSS/XPath selector for a product link.

    Usage: /update_selector <link_id> <selector>
    """
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "📝 <b>Format:</b>\n"
            "<code>/update_selector [link_id] [css_selector]</code>\n\n"
            "<b>Contoh:</b>\n"
            "<code>/update_selector 5 div.price span</code>",
            parse_mode="HTML",
        )
        return

    try:
        link_id = int(parts[1])
    except ValueError:
        await message.answer("❌ link_id harus berupa angka.")
        return

    selector = parts[2].strip()
    if not selector:
        await message.answer("❌ Selector tidak boleh kosong.")
        return

    try:
        await crud.update_link_selector(link_id, selector)
        await message.answer(
            f"✅ Selector untuk link #{link_id} berhasil diperbarui:\n"
            f"<code>{selector}</code>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to update selector")
        await message.answer("❌ Gagal memperbarui selector. Pastikan link_id valid.")
