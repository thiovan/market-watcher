# Market Watcher Bot - Project Context

This document provides a comprehensive overview of the `market-watcher` project's architecture, recent optimizations, and current state. It is designed to act as context for future development or analysis by other AI assistants.

## 1. Project Overview

**Market Watcher** is a Telegram bot designed to monitor and scrape product prices from Indonesian e-commerce platforms (Tokopedia and Shopee) and notify users when prices drop, reach a target, or hit a historical low.

### Core Technologies

- **Python 3.10+**
- **aiogram (v3)**: For handling Telegram Bot API interactions (Command handlers, FSM, Callbacks, Middleware).
- **Playwright (async) & playwright-stealth**: For headless browser scraping to bypass anti-bot protections.
- **aiosqlite**: For asynchronous SQLite database operations to store products, links, price history, and alert rules.
- **APScheduler (AsyncIOScheduler)**: For running periodic price checks in the background.

## 2. Web Scraping & Anti-Bot Strategy (`scrapers/browser.py`, `tokopedia.py`, `shopee.py`)

To successfully scrape Tokopedia and Shopee on a low-spec VPS (e.g., 1GB RAM) without getting blocked:

- **Singleton Browser**: A single `playwright.chromium` instance is kept alive in the background. For each scrape, only a new `Context` and `Page` are created and destroyed to save CPU/RAM.
- **Playwright Stealth**: Injected into every page to remove webdriver fingerprints.
- **User-Agent Rotation**: The browser randomly selects from a pool of modern User-Agents to avoid static fingerprinting.
- **Aggressive Resource Blocking**: The browser aborts requests for `image`, `media`, `font`, and `stylesheet` resource types, as well as known tracker domains (Google Analytics, Hotjar, Sentry, etc.). This prevents downloading heavy product images and saves massive amounts of bandwidth and memory.
- **Stealth Login (Cookies)**: Users can upload encrypted Tokopedia/Shopee cookies via the `/setcookies` command to bypass strict login walls.
- **Extraction Logic**:
  - **Tokopedia**: Prioritizes extracting pure JSON data (`__INITIAL_STATE__`) over DOM parsing. If JSON fails, it falls back to parsing the rendered HTML body or using a TreeWalker to find the largest "Rp" text on the screen.
  - **Shopee**: Delays execution slightly to allow Vue/React to render, then uses Regex on the HTML content. If that fails, it uses a TreeWalker to find prices > Rp100,000 to avoid misinterpreting cheap shipping costs or vouchers as the main product price.

## 3. SQLite Database Optimizations (`db/database.py`, `db/models.py`)

The database has been heavily optimized for concurrent reads/writes on a VPS:

- **WAL Mode**: `PRAGMA journal_mode=WAL` is enabled to allow concurrent readers without blocking writers.
- **Reduced Sync**: `PRAGMA synchronous=NORMAL` is set to reduce disk I/O bottlenecks.
- **Datetime Storage**: Timestamps are stored purely as `YYYY-MM-DD HH:MM:SS` (UTC) strings. Python's `isoformat()` with timezone (`+00:00`) strings were removed because they break SQLite's native `datetime()` math functions used by the scheduler.

## 4. Scheduler & Queue Logic (`scheduler/jobs.py`, `bot/main.py`)

To prevent the VPS CPU from pinning at 100% when checking dozens of links:

- **Master Interval**: The APScheduler wakes up every `CHECK_INTERVAL_MINUTES` (Default: 15 mins).
- **Product Interval**: Each product has its own `check_interval_minutes` (Default: 120 mins, customizable via Telegram).
- **Batch Queries**: When the scheduler wakes up, it queries SQLite for links where `last_checked + interval <= now`.
- **Throttling**: The scraper waits `SCRAPE_DELAY_SECONDS` (10s) between links of the same product, and `SCRAPE_BATCH_DELAY_SECONDS` (30s) between different products.

## 5. Security Enhancements

- **Encrypted Storage**: Cookies uploaded via Telegram are encrypted using AES-GCM (derived from the `BOT_TOKEN`) before being saved to the `data/` folder as `*_cookies.enc`.
- **SSRF/XSS Prevention**: The `/add` command handler strictly validates that only URLs starting with `http` and originating from `tokopedia.com` or `shopee.co.id` domains are allowed.
- **Token Masking**: External library logs (`httpx`, `aiogram.event`) are silenced to `WARNING` level to prevent connection error tracebacks from accidentally leaking the `BOT_TOKEN` in the VPS terminal logs.
- **Admin Only**: Middlewares ensure only the user specified in `ADMIN_USER_ID` can interact with the bot.

## 6. Reliability & Bug Fixes (Recent Changes)

- **Price Anomaly Detection**: If a marketplace glitches and returns a price that is >80% lower than the previously recorded price (e.g., dropping from 1.000.000 to 5.000), the bot identifies it as a scraper anomaly and ignores it. This prevents spamming "Price Drop!" notifications for fake Rp0/Rp99 flash sales.
- **Consecutive Failure Alerts**: A `fail_count` is tracked per link. If a link fails to scrape 3 times in a row, the bot sends an alert to the user suggesting they check the link manually.
- **Timezone Formatting**: History messages (`/history` and inline callbacks) now correctly convert UTC database timestamps into the VPS server's local machine timezone (`astimezone()`).
