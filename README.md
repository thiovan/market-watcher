# 🛒 Market Watcher Bot

Bot Telegram untuk memantau harga produk marketplace (Tokopedia & Shopee) secara otomatis. Dioptimalkan untuk VPS berspesifikasi rendah.

## ✨ Fitur

- 📦 **Multi-link tracking** — Satu produk bisa dipantau dari beberapa marketplace
- 🔔 **3 jenis notifikasi** — Harga Turun, Target Harga, & Rekor Termurah
- 🛡️ **Anti-detection scraping** — Playwright + stealth plugin untuk bypass anti-bot
- 🍪 **Cookie management via Telegram** — Set dan kelola cookies langsung dari chat
- 🔒 **Encrypted cookie storage** — Cookies terenkripsi (Fernet/AES) di disk
- 🔐 **Admin-only access** — Hanya admin yang bisa menggunakan bot
- 📊 **Riwayat harga + source tracking** — Histori harga dengan indikator 🍪/🌐
- 🚀 **Browser singleton** — Satu Chromium untuk semua request (hemat RAM)
- ⏱️ **Interval fleksibel** — Atur frekuensi cek per produk (30 menit - 24 jam)
- 🔧 **100% via Telegram** — Semua kontrol lewat chat

## 🛠️ Tech Stack

| Komponen      | Teknologi             |
| ------------- | --------------------- |
| Bot Framework | aiogram 3 (async)     |
| Database      | SQLite + aiosqlite    |
| Scraping      | Playwright + stealth  |
| Encryption    | cryptography (Fernet) |
| HTTP Client   | httpx                 |
| Scheduler     | APScheduler           |
| Bahasa        | Python 3.10+          |

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone <repo-url> market-watcher
cd market-watcher
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Linux
pip install -e .
playwright install chromium
```

### 2. Konfigurasi

```bash
copy .env.example .env
# Edit .env dan isi BOT_TOKEN serta ADMIN_USER_ID
```

| Variable                 | Deskripsi                                          |
| ------------------------ | -------------------------------------------------- |
| `BOT_TOKEN`              | Token dari [@BotFather](https://t.me/BotFather)    |
| `ADMIN_USER_ID`          | Telegram User ID Anda                              |
| `CHECK_INTERVAL_MINUTES` | Interval default (default: 240)                    |
| `DATABASE_PATH`          | Path file SQLite (default: data/market_watcher.db) |

### 3. Jalankan

```bash
python run.py
```

## 📱 Perintah Bot

| Perintah                 | Fungsi                           |
| ------------------------ | -------------------------------- |
| `/start`                 | Pesan selamat datang             |
| `/add`                   | Tambah produk baru (multi-step)  |
| `/list`                  | Lihat watchlist & harga terbaru  |
| `/check`                 | Cek harga sekarang (manual)      |
| `/check <id>`            | Cek produk tertentu              |
| `/history <id>`          | Lihat riwayat perubahan harga    |
| `/cookies`               | Lihat status cookies             |
| `/setcookies <platform>` | Set cookies (paste dari browser) |
| `/delcookies <platform>` | Hapus cookies                    |
| `/settings`              | Atur frekuensi pengecekan        |
| `/help`                  | Panduan penggunaan               |

## 🍪 Setup Cookies

Shopee **membutuhkan** cookies untuk scraping. Tokopedia bisa tanpa cookies (opsional untuk keandalan lebih baik).

### Via Telegram (Recommended)

1. Install extension **Cookie-Editor** di Chrome/Firefox
2. Buka & login ke marketplace
3. Klik Cookie-Editor → **Export** → copy JSON
4. Di Telegram: `/setcookies shopee` → paste JSON
5. Jika JSON terlalu panjang & terpecah, kirim semua bagian lalu ketik `/done`

### Via File (Manual)

Cookies otomatis terenkripsi saat disimpan. File terenkripsi: `data/shopee_cookies.enc`.
File plaintext lama (`.json`) otomatis dimigrasi ke format terenkripsi.

### Source Tracking

Setiap harga yang diambil dilacak sumbernya:

- 🍪 = Harga diambil menggunakan cookies
- 🌐 = Harga diambil tanpa cookies

Indikator ini tampil di `/check` dan `/history`.

## 🏗️ Struktur Proyek

```
market-watcher/
├── run.py                  # Entry point
├── config.py               # Settings loader
├── db/                     # Database (SQLite + migration)
│   ├── models.py           # Schema DDL
│   ├── crud.py             # CRUD operations
│   └── database.py         # Connection + auto-migration
├── scrapers/               # Marketplace scrapers
│   ├── base.py             # BaseScraper + PriceResult
│   ├── browser.py          # Chromium singleton (shared)
│   ├── cookie_manager.py   # Encrypted cookie storage
│   ├── tokopedia.py        # Tokopedia (Playwright+stealth)
│   ├── shopee.py           # Shopee (Playwright+stealth+cookies)
│   └── url_parser.py       # URL parsing utilities
├── bot/                    # Telegram bot
│   ├── middleware.py       # Admin-only access control
│   └── handlers/
│       ├── add.py          # /add command flow
│       ├── check_history.py # /check & /history
│       ├── cookies.py      # /cookies, /setcookies, /delcookies
│       ├── watchlist.py    # /list
│       ├── settings.py     # /settings
│       └── start.py        # /start & /help
├── scheduler/              # Background price checker
│   └── jobs.py
├── data/                   # Encrypted cookies & database
└── tests/                  # Unit tests
```

## 🔒 Keamanan

- **Encrypted cookies** — Cookies dienkripsi menggunakan Fernet (AES-128-CBC). Key diturunkan dari `BOT_TOKEN`.
- **Admin-only** — Semua perintah hanya bisa diakses oleh `ADMIN_USER_ID`.
- **Domain validation** — Hanya cookies dengan domain yang sesuai platform yang diterima.
- **Buffer limit** — Paste cookie dibatasi 100KB untuk mencegah memory exhaustion.
- **Migrasi otomatis** — File cookie plaintext lama otomatis dienkripsi saat startup.

## 🧪 Testing

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## 📋 Deployment (VPS)

### 1. Install System Dependencies (Chromium)

Playwright membutuhkan shared libraries untuk menjalankan Chromium. Jalankan:

```bash
# Otomatis install semua dependencies Chromium
playwright install-deps chromium

# Atau install manual jika perintah di atas gagal:
sudo apt-get update && sudo apt-get install -y \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libnspr4 libnss3 \
    libxshmfence1 xvfb
```

Lalu install Chromium browser:

```bash
playwright install chromium
```

### 2. Systemd Service

```bash
sudo nano /etc/systemd/system/market-watcher.service
```

```ini
[Unit]
Description=Market Watcher Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/market-watcher
ExecStart=/root/market-watcher/.venv/bin/python run.py
Restart=always
RestartSec=10
Environment=DISPLAY=:99

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable market-watcher
sudo systemctl start market-watcher
```

> **Note:** Jika Chromium membutuhkan display (error "no display"), gunakan `xvfb-run`:
>
> ```ini
> ExecStart=/usr/bin/xvfb-run /root/market-watcher/.venv/bin/python run.py
> ```
