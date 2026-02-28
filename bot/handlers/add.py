"""/add command handler — FSM multi-step product addition."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import alert_type_keyboard, more_links_keyboard
from bot.states.add_product import AddProductStates
from db import crud
from scrapers.url_parser import detect_platform

logger = logging.getLogger(__name__)

router = Router(name="add")


# ---------------------------------------------------------------------------
# Step 1: /add → ask product name
# ---------------------------------------------------------------------------

@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    """Start the add-product flow."""
    await state.clear()
    await state.set_state(AddProductStates.waiting_name)
    await message.answer(
        "📦 <b>Tambah Produk Baru</b>\n\n"
        "Silakan kirim <b>nama produk</b> yang ingin dipantau.\n"
        "Contoh: <i>iPhone 16 Pro Max</i>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Step 2: receive name → ask first link
# ---------------------------------------------------------------------------

@router.message(AddProductStates.waiting_name)
async def receive_name(message: Message, state: FSMContext) -> None:
    """Receive the product name and ask for the first link."""
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ Nama tidak boleh kosong. Coba lagi:")
        return

    await state.update_data(product_name=name, links=[])
    await state.set_state(AddProductStates.waiting_link)
    await message.answer(
        f"✅ Nama produk: <b>{name}</b>\n\n"
        "Sekarang kirim <b>link marketplace</b> pertama.\n"
        "Contoh: <i>https://www.tokopedia.com/toko/produk-xyz</i>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Step 3: receive link → ask more links?
# ---------------------------------------------------------------------------

@router.message(AddProductStates.waiting_link)
async def receive_link(message: Message, state: FSMContext) -> None:
    """Receive a marketplace link and validate it."""
    url = (message.text or "").strip()
    if not url.startswith(("http://", "https://")):
        await message.answer(
            "❌ Format URL tidak valid. Harus dimulai dengan <code>http://</code> atau <code>https://</code>.\n"
            "Silakan kirim ulang:",
            parse_mode="HTML",
        )
        return

    platform = detect_platform(url)
    data = await state.get_data()
    links: list[dict] = data.get("links", [])
    links.append({"url": url, "platform": platform})
    await state.update_data(links=links)

    platform_label = {"tokopedia": "Tokopedia 🟢", "shopee": "Shopee 🟠"}.get(
        platform, f"Unknown ({platform}) ⚪"
    )
    await message.answer(
        f"🔗 Link #{len(links)} ditambahkan — {platform_label}\n\n"
        "Apakah ingin menambah link marketplace lain untuk produk ini?",
        reply_markup=more_links_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(AddProductStates.waiting_more_links)


# ---------------------------------------------------------------------------
# Step 3b: more links callback
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "more_links:yes")
async def cb_more_links_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """User wants to add another link."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
    await state.set_state(AddProductStates.waiting_link)
    await callback.message.answer(  # type: ignore[union-attr]
        "🔗 Kirim link marketplace berikutnya:"
    )


@router.callback_query(F.data == "more_links:no")
async def cb_more_links_no(callback: CallbackQuery, state: FSMContext) -> None:
    """User is done adding links — ask for alert type."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
    await state.set_state(AddProductStates.waiting_alert_type)
    await state.update_data(alert_rules=[])
    await callback.message.answer(  # type: ignore[union-attr]
        "🔔 <b>Pengaturan Notifikasi</b>\n\n"
        "Pilih jenis notifikasi yang diinginkan.\n"
        "Anda bisa memilih lebih dari satu. Tekan <b>✅ Selesai</b> jika sudah.",
        reply_markup=alert_type_keyboard(),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Step 4: choose alert type(s)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("alert:"))
async def cb_alert_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle alert type selection."""
    action = callback.data.split(":")[1]  # type: ignore[union-attr]
    await callback.answer()

    if action == "DONE":
        # Finalize: save to DB
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
        await _save_product(callback, state)
        return

    if action == "TARGET_PRICE":
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
        await state.set_state(AddProductStates.waiting_target_price)
        await callback.message.answer(  # type: ignore[union-attr]
            "🎯 Masukkan target harga (angka saja, tanpa Rp).\n"
            "Contoh: <code>14500000</code>",
            parse_mode="HTML",
        )
        return

    # PRICE_DROP or HISTORICAL_LOW
    data = await state.get_data()
    rules: list[dict] = data.get("alert_rules", [])

    # Avoid duplicates
    if not any(r["type"] == action for r in rules):
        rules.append({"type": action, "value": None})
        await state.update_data(alert_rules=rules)

    labels = {"PRICE_DROP": "🔻 Harga Turun", "HISTORICAL_LOW": "📉 Rekor Termurah"}
    selected = ", ".join(labels.get(r["type"], r["type"]) for r in rules)
    await callback.message.answer(  # type: ignore[union-attr]
        f"✅ Notifikasi dipilih: {selected}\n\n"
        "Pilih lagi atau tekan <b>✅ Selesai</b>.",
        reply_markup=alert_type_keyboard(),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Step 4b: receive target price
# ---------------------------------------------------------------------------

@router.message(AddProductStates.waiting_target_price)
async def receive_target_price(message: Message, state: FSMContext) -> None:
    """Receive the target price value."""
    text = (message.text or "").strip().replace(".", "").replace(",", "")
    if not text.isdigit():
        await message.answer(
            "❌ Masukkan angka saja. Contoh: <code>14500000</code>",
            parse_mode="HTML",
        )
        return

    target = int(text)
    data = await state.get_data()
    rules: list[dict] = data.get("alert_rules", [])
    rules.append({"type": "TARGET_PRICE", "value": target})
    await state.update_data(alert_rules=rules)
    await state.set_state(AddProductStates.waiting_alert_type)

    await message.answer(
        f"🎯 Target harga: <b>Rp{target:,.0f}</b>\n\n"
        "Pilih notifikasi lain atau tekan <b>✅ Selesai</b>.",
        reply_markup=alert_type_keyboard(),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Save product to DB + initial price fetch
# ---------------------------------------------------------------------------

async def _save_product(callback: CallbackQuery, state: FSMContext) -> None:
    """Persist the product, links, and alert rules to the database."""
    data = await state.get_data()
    user_id = callback.from_user.id
    name = data.get("product_name", "Unknown")
    links = data.get("links", [])
    rules = data.get("alert_rules", [])

    try:
        product_id = await crud.add_product(name, user_id)

        for link in links:
            await crud.add_product_link(product_id, link["url"], link["platform"])

        for rule in rules:
            await crud.add_alert_rule(product_id, rule["type"], rule.get("value"))

        links_summary = "\n".join(
            f"  • {l['platform'].title()}: {l['url']}" for l in links
        )
        rules_labels = {
            "PRICE_DROP": "🔻 Harga Turun",
            "TARGET_PRICE": "🎯 Target Harga",
            "HISTORICAL_LOW": "📉 Rekor Termurah",
        }
        rules_summary = ", ".join(
            rules_labels.get(r["type"], r["type"])
            + (f" (Rp{r['value']:,.0f})" if r.get("value") else "")
            for r in rules
        )

        await callback.message.answer(  # type: ignore[union-attr]
            f"🎉 <b>Produk berhasil ditambahkan!</b>\n\n"
            f"📦 <b>{name}</b>\n"
            f"🔗 Links:\n{links_summary}\n"
            f"🔔 Notifikasi: {rules_summary or 'Tidak ada'}\n\n"
            f"⏳ <i>Mengambil harga awal...</i>",
            parse_mode="HTML",
        )

        # Trigger initial price fetch in the background
        asyncio.create_task(_initial_price_fetch(callback, product_id, name, user_id))

    except Exception:
        logger.exception("Failed to save product")
        await callback.message.answer(  # type: ignore[union-attr]
            "❌ Terjadi kesalahan saat menyimpan produk. Silakan coba lagi."
        )
    finally:
        await state.clear()


async def _initial_price_fetch(
    callback: CallbackQuery, product_id: int, name: str, user_id: int
) -> None:
    """Fetch initial prices right after product is added."""
    from aiogram import Bot
    from scheduler.jobs import check_product_links, fmt_price

    bot: Bot = callback.bot  # type: ignore[assignment]

    try:
        results = await check_product_links(bot, product_id, user_id)

        parts: list[str] = [f"✅ <b>Harga awal — {name}</b>\n"]
        for r in results:
            platform = r["platform"].title()
            new = r["new_price"]
            if new is None:
                parts.append(f"  ❌ {platform}: Gagal mengambil harga")
            else:
                parts.append(f"  💰 {platform}: <b>{fmt_price(new)}</b>")

        parts.append("\n<i>Gunakan /list untuk melihat watchlist.</i>")
        await bot.send_message(
            chat_id=user_id,
            text="\n".join(parts),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Initial price fetch failed for product %s", product_id)
