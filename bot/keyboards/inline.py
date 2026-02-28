"""Inline keyboard builders for the bot."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# ---------------------------------------------------------------------------
# Alert type selection
# ---------------------------------------------------------------------------

def alert_type_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for choosing alert notification rules."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔻 Harga Turun", callback_data="alert:PRICE_DROP")],
            [InlineKeyboardButton(text="🎯 Target Harga (Rp)", callback_data="alert:TARGET_PRICE")],
            [InlineKeyboardButton(text="📉 Rekor Termurah", callback_data="alert:HISTORICAL_LOW")],
            [InlineKeyboardButton(text="✅ Selesai", callback_data="alert:DONE")],
        ]
    )


# ---------------------------------------------------------------------------
# Add more links
# ---------------------------------------------------------------------------

def more_links_keyboard() -> InlineKeyboardMarkup:
    """Keyboard asking if user wants to add another marketplace link."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Tambah Link", callback_data="more_links:yes"),
                InlineKeyboardButton(text="▶️ Lanjut", callback_data="more_links:no"),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Watchlist actions
# ---------------------------------------------------------------------------

def watchlist_item_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Action buttons for a product in the watchlist."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Detail", callback_data=f"detail:{product_id}"),
                InlineKeyboardButton(text="📈 Riwayat", callback_data=f"history:{product_id}"),
            ],
            [
                InlineKeyboardButton(text="🔄 Cek Harga", callback_data=f"check:{product_id}"),
                InlineKeyboardButton(text="⏱️ Interval", callback_data=f"interval:{product_id}"),
                InlineKeyboardButton(text="🗑️ Hapus", callback_data=f"delete:{product_id}"),
            ]
        ]
    )


def confirm_delete_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Confirmation keyboard for deleting a product."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ya, Hapus", callback_data=f"confirm_delete:{product_id}"),
                InlineKeyboardButton(text="❌ Batal", callback_data="cancel"),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Interval selection
# ---------------------------------------------------------------------------

def interval_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Keyboard for choosing price check interval."""
    intervals = [
        ("30 Menit", 30),
        ("1 Jam", 60),
        ("2 Jam", 120),
        ("4 Jam", 240),
        ("12 Jam", 720),
        ("24 Jam", 1440),
    ]
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"set_interval:{product_id}:{mins}")]
        for label, mins in intervals
    ]
    buttons.append([InlineKeyboardButton(text="❌ Batal", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
