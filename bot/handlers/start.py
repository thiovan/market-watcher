"""/start and /help command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="start")

WELCOME_TEXT = """
🛒 <b>Market Watcher Bot</b> <i>v1.2.0</i>

Selamat datang! Saya adalah bot pelacak harga marketplace.
Saya akan memantau harga produk dari <b>Tokopedia</b> & <b>Shopee</b> dan mengirim notifikasi saat harga berubah.

<b>Perintah yang tersedia:</b>
/add — Tambah produk baru ke watchlist
/list — Lihat daftar produk yang dipantau
/check — Cek harga sekarang (manual)
/history — Lihat riwayat perubahan harga
/cookies — Kelola cookies untuk scraping
/settings — Atur frekuensi pengecekan
/help — Tampilkan bantuan ini

<i>Mulai dengan mengirim /add untuk menambah produk pertama!</i>
"""

HELP_TEXT = """
📖 <b>Panduan Penggunaan</b>

<b>1. Menambah Produk</b>
Kirim /add lalu ikuti langkah-langkah:
• Masukkan nama produk (misal: "iPhone 16")
• Kirim link Tokopedia/Shopee
• Tambah link marketplace lain (opsional)
• Pilih jenis notifikasi yang diinginkan

<b>2. Jenis Notifikasi</b>
🔻 <b>Harga Turun</b> — Notif setiap harga turun dari cek sebelumnya
🎯 <b>Target Harga</b> — Notif saat harga mencapai target Rp tertentu
📉 <b>Rekor Termurah</b> — Notif saat harga menyentuh titik terendah sepanjang masa

<b>3. Cek Harga Manual</b>
Kirim /check untuk mengecek harga semua produk sekarang juga.
Atau /check [id] untuk cek produk tertentu.

<b>4. Riwayat Harga</b>
Kirim /history [id] untuk melihat riwayat perubahan harga lengkap.

<b>5. Melihat Watchlist</b>
Kirim /list untuk melihat semua produk yang dipantau beserta harga terakhir.

<b>6. Mengatur Interval</b>
Kirim /settings atau klik tombol ⏱️ di /list untuk mengatur frekuensi pengecekan harga.

<b>7. Kelola Cookies</b>
Kirim /cookies untuk melihat status cookies.
Kirim <code>/setcookies shopee</code> lalu paste JSON dari Cookie-Editor.
Cookies meningkatkan keberhasilan scraping (wajib untuk Shopee).

<b>8. Update Selector</b>
Jika scraping gagal, kirim:
<code>/update_selector [link_id] [css_selector]</code>
untuk memperbarui selector CSS/XPath.
"""


@router.message(Command("start", "menu"))
async def cmd_start(message: Message) -> None:
    """Handle /start and /menu commands."""
    await message.answer(WELCOME_TEXT, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(HELP_TEXT, parse_mode="HTML")
