"""Shared Playwright browser singleton for efficient resource usage.

Instead of launching a new Chromium process per fetch (~150MB each),
this module maintains a single reusable browser instance.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_browser = None
_playwright = None
_lock = asyncio.Lock()


async def get_browser():
    """Get or create the shared Chromium browser instance."""
    global _browser, _playwright

    async with _lock:
        # Return existing if alive
        if _browser is not None and _browser.is_connected():
            return _browser

        # Clean up dead instance
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None

        if _playwright is not None:
            try:
                await _playwright.stop()
            except Exception:
                pass
            _playwright = None

        # Launch new
        from playwright.async_api import async_playwright
        from config import settings as app_settings
        _playwright = await async_playwright().start()

        headless = app_settings.headless
        logger.info("Launching Chromium (headless=%s)", headless)

        try:
            _browser = await _playwright.chromium.launch(
                headless=headless,
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-sync",
                    "--disable-http2",
                    "--no-first-run",
                ],
            )
        except Exception:
            # Fallback to bundled Chromium
            _browser = await _playwright.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-http2",
                ],
            )

        logger.info("Playwright browser launched (singleton)")
        return _browser


async def create_stealth_context(*, cookies: list[dict] | None = None):
    """Create a new browser context with stealth applied.

    Returns (context, page) tuple. Caller must close the context when done.
    """
    import random
    from playwright_stealth import Stealth

    # Pool of modern User-Agents to rotate
    # This prevents anti-bot systems from fingerprinting a single static UA over time
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"
    ]

    browser = await get_browser()
    stealth = Stealth()

    context = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=random.choice(USER_AGENTS),
        locale="id-ID",
        timezone_id="Asia/Jakarta",
    )

    if cookies:
        await context.add_cookies(cookies)

    page = await context.new_page()
    await stealth.apply_stealth_async(page)

    # Block heavy resources to save memory, CPU & bandwidth
    # We block by resource_type instead of extension because many marketplace
    # images have query params (e.g. ?ect=4g) and don't end in .jpg/.png
    _BLOCKED_TYPES = {"image", "media", "font", "stylesheet"}
    _BLOCKED_DOMAINS = (
        "googletagmanager", "google-analytics", "analytics",
        "doubleclick.net", "hotjar.com", "sentry.io",
        "adsense", "tracker", "pixel",
    )

    async def _block_resources(route):
        req = route.request
        # Block by resource type (catches all images regardless of URL structure)
        if req.resource_type in _BLOCKED_TYPES:
            return await route.abort()
        # Block known trackers/analytics by domain
        url = req.url.lower()
        if any(d in url for d in _BLOCKED_DOMAINS):
            return await route.abort()
        await route.continue_()

    await page.route("**/*", _block_resources)

    return context, page


async def close_browser() -> None:
    """Gracefully close the shared browser instance."""
    global _browser, _playwright

    async with _lock:
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None

        if _playwright is not None:
            try:
                await _playwright.stop()
            except Exception:
                pass
            _playwright = None

        logger.info("Playwright browser closed")
