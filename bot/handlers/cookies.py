"""/cookies, /setcookies, /delcookies command handlers.

Manage marketplace cookies from Telegram.
Users can paste Cookie-Editor JSON exports directly in the chat.
Handles Telegram message splitting: accumulates text until valid JSON.
"""

from __future__ import annotations

import json
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from scrapers.cookie_manager import (
    PLATFORMS,
    delete_cookies,
    get_cookie_info,
    save_cookies,
)

logger = logging.getLogger(__name__)

router = Router(name="cookies")

# Max accumulated buffer size (100KB) to prevent memory abuse
_MAX_BUFFER_SIZE = 100 * 1024


class CookieState(StatesGroup):
    """FSM states for cookie paste flow."""
    waiting_for_paste = State()


# ---------------------------------------------------------------------------
# /cookies — Show cookie status
# ---------------------------------------------------------------------------

@router.message(Command("cookies"))
async def cmd_cookies(message: Message) -> None:
    """Show cookie status for all platforms."""
    lines = ["🍪 <b>Status Cookies</b>\n"]

    for platform in PLATFORMS:
        info = get_cookie_info(platform)
        name = platform.title()
        if info["exists"]:
            lines.append(
                f"  ✅ <b>{name}</b>: {info['count']} cookies "
                f"(update: {info['modified']})"
            )
        else:
            lines.append(f"  ❌ <b>{name}</b>: Belum ada cookies")

    lines.append("\n<b>Perintah:</b>")
    lines.append("  <code>/setcookies shopee</code> — Set cookies Shopee")
    lines.append("  <code>/setcookies tokopedia</code> — Set cookies Tokopedia")
    lines.append("  <code>/delcookies shopee</code> — Hapus cookies Shopee")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ---------------------------------------------------------------------------
# /setcookies — Start cookie paste flow
# ---------------------------------------------------------------------------

@router.message(Command("setcookies"))
async def cmd_setcookies(message: Message, state: FSMContext) -> None:
    """Start the cookie paste flow for a platform.

    Usage: /setcookies <platform>
    """
    parts = (message.text or "").split()

    if len(parts) < 2:
        platforms = ", ".join(f"<code>{p}</code>" for p in PLATFORMS)
        await message.answer(
            f"❌ Pilih platform: {platforms}\n"
            f"Format: <code>/setcookies shopee</code>",
            parse_mode="HTML",
        )
        return

    platform = parts[1].lower()
    if platform not in PLATFORMS:
        platforms = ", ".join(f"<code>{p}</code>" for p in PLATFORMS)
        await message.answer(
            f"❌ Platform tidak dikenal: <code>{platform}</code>\n"
            f"Platform tersedia: {platforms}",
            parse_mode="HTML",
        )
        return

    await state.set_state(CookieState.waiting_for_paste)
    await state.update_data(platform=platform, buffer="")

    await message.answer(
        f"🍪 <b>Set Cookies {platform.title()}</b>\n\n"
        f"Paste JSON cookies dari <b>Cookie-Editor</b> di bawah ini.\n\n"
        f"<b>Cara export:</b>\n"
        f"1. Buka {platform.title()} di browser & login\n"
        f"2. Klik icon Cookie-Editor → <b>Export</b> → <b>JSON</b>\n"
        f"3. Paste hasilnya di sini\n\n"
        f"💡 <i>Jika JSON terlalu panjang dan terpecah jadi beberapa pesan, "
        f"kirim semua bagian lalu ketik</i> <code>/done</code>\n\n"
        f"Ketik /cancel untuk membatalkan.",
        parse_mode="HTML",
    )


# Handle pasted cookie JSON (accumulates split messages)
@router.message(CookieState.waiting_for_paste, F.text)
async def handle_cookie_paste(message: Message, state: FSMContext) -> None:
    """Process pasted cookie JSON, accumulating split messages."""
    text = (message.text or "").strip()

    # Cancel
    if text.lower() in ("/cancel", "cancel", "batal"):
        await state.clear()
        await message.answer("❌ Dibatalkan.")
        return

    data = await state.get_data()
    platform = data.get("platform", "")
    buffer = data.get("buffer", "")

    # /done — try to parse accumulated buffer
    if text.lower() == "/done":
        if not buffer:
            await message.answer(
                "❌ Belum ada data. Paste JSON cookies terlebih dahulu.",
            )
            return
        return await _try_save_cookies(message, state, platform, buffer)

    # Accumulate text into buffer (with size limit)
    buffer += text
    if len(buffer) > _MAX_BUFFER_SIZE:
        await state.clear()
        await message.answer(
            f"❌ Data terlalu besar (max {_MAX_BUFFER_SIZE // 1024}KB).\n"
            f"Gunakan <code>/setcookies {platform}</code> untuk coba lagi.",
            parse_mode="HTML",
        )
        return
    await state.update_data(buffer=buffer)

    # Try to parse immediately — if valid JSON, save right away
    try:
        parsed = json.loads(buffer)
        if isinstance(parsed, list):
            # Complete and valid JSON array — save immediately
            return await _try_save_cookies(message, state, platform, buffer)
    except json.JSONDecodeError:
        pass

    # Check if it looks like an incomplete JSON array
    stripped = buffer.strip()
    if stripped.startswith("[") and not stripped.endswith("]"):
        await message.answer(
            "📥 Diterima, menunggu bagian selanjutnya...\n"
            "Kirim bagian berikutnya atau ketik /done jika sudah selesai.",
        )
    elif not stripped.startswith("["):
        # Doesn't look like JSON at all — try to save and let it fail with a good message
        return await _try_save_cookies(message, state, platform, buffer)
    else:
        # Ends with ] but still invalid — try saving
        return await _try_save_cookies(message, state, platform, buffer)


async def _try_save_cookies(
    message: Message, state: FSMContext, platform: str, raw_json: str,
) -> None:
    """Attempt to save accumulated cookie JSON."""
    success, msg = save_cookies(platform, raw_json)
    await state.clear()

    if success:
        info = get_cookie_info(platform)
        await message.answer(
            f"✅ {msg}\n"
            f"🍪 Total: {info['count']} cookies\n\n"
            f"Gunakan /check untuk menguji scraping.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❌ Gagal: {msg}\n\n"
            f"Pastikan format JSON valid dari Cookie-Editor.\n"
            f"Gunakan <code>/setcookies {platform}</code> untuk coba lagi.",
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# /delcookies — Delete cookies
# ---------------------------------------------------------------------------

@router.message(Command("delcookies"))
async def cmd_delcookies(message: Message) -> None:
    """Delete cookies for a platform.

    Usage: /delcookies <platform>
    """
    parts = (message.text or "").split()

    if len(parts) < 2:
        platforms = ", ".join(f"<code>{p}</code>" for p in PLATFORMS)
        await message.answer(
            f"❌ Pilih platform: {platforms}\n"
            f"Format: <code>/delcookies shopee</code>",
            parse_mode="HTML",
        )
        return

    platform = parts[1].lower()
    if platform not in PLATFORMS:
        await message.answer(
            f"❌ Platform tidak dikenal: <code>{platform}</code>",
            parse_mode="HTML",
        )
        return

    success, msg = delete_cookies(platform)
    emoji = "✅" if success else "❌"
    await message.answer(f"{emoji} {msg}")
