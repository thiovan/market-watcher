"""Shopee price scraper — Playwright + stealth with cookie support.

Shopee requires cookies for reliable access. Uses shared browser singleton.
Cookie file must be set via /setcookies shopee or data/shopee_cookies.enc.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter

from scrapers.base import BaseScraper, PriceResult
from scrapers.browser import create_stealth_context
from scrapers.cookie_manager import has_cookies, load_cookies_playwright
from scrapers.url_parser import extract_shopee_params

logger = logging.getLogger(__name__)


class ShopeeScraper(BaseScraper):
    """Fetch product price from Shopee using shared browser + stealth + cookies."""

    async def fetch_price(self, url: str) -> PriceResult:
        params = extract_shopee_params(url)
        if params is None:
            logger.warning("Cannot extract Shopee params from URL: %s", url)
            return PriceResult(price=None)

        if not has_cookies("shopee"):
            logger.warning(
                "Shopee membutuhkan cookies. Gunakan /setcookies shopee"
            )
            return PriceResult(price=None)

        return await self._fetch(url)

    async def _fetch(self, url: str) -> PriceResult:
        """Load page via shared browser and extract price."""
        cookies = load_cookies_playwright("shopee")

        try:
            context, page = await create_stealth_context(cookies=cookies or None)

            try:
                logger.info("Loading Shopee [cookies]: %s", url[:80])

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as nav_err:
                    logger.warning("Shopee nav retry: %s", str(nav_err)[:80])
                    await asyncio.sleep(2)
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        logger.warning("Shopee navigation failed")

                # Smart wait: Shopee renders variant/shipping prices first.
                # Look for a price ≥ 1M (7+ digits) which indicates product price area is loaded.
                try:
                    await page.wait_for_function(
                        """() => {
                            if (!document.body) return false;
                            const text = document.body.innerText;
                            const matches = text.match(/Rp\\s*[\\d.]{7,}/g);
                            return matches && matches.length >= 2;
                        }""",
                        timeout=15000,
                    )
                except Exception:
                    pass  # Timeout OK — try extracting anyway

                # Extra wait for React components to settle
                await asyncio.sleep(3)

                # Check for CAPTCHA or login redirect
                current_url = page.url
                if "captcha" in current_url or "login" in current_url:
                    logger.warning(
                        "Shopee CAPTCHA/login — cookies expired. "
                        "Gunakan /setcookies shopee untuk update."
                    )
                    return PriceResult(price=None)

                price = await self._extract_price(page)

                if price:
                    logger.info("Shopee price [cookies]: %d", price)
                    return PriceResult(price=price, used_cookies=True)

                return PriceResult(price=None)

            finally:
                await context.close()

        except Exception:
            logger.exception("Shopee fetch failed for %s", url[:80])
            return PriceResult(price=None)

    async def _extract_price(self, page) -> int | None:
        """Extract product price from rendered Shopee page."""
        # Strategy 1: Regex on rendered HTML — most reliable
        # Product price appears first in the HTML, before shipping/voucher noise
        try:
            content = await page.content()
            matches = re.findall(r'Rp\s*[\d.]+(?:\.\d{3})+', content)
            if matches:
                for m in matches:
                    price = self.parse_price(m)
                    if price and price >= 100_000:
                        return price
        except Exception:
            pass

        # Strategy 2: DOM text nodes (fallback)
        try:
            price_text = await page.evaluate(r"""
                () => {
                    const prices = [];
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null, false
                    );
                    while (walker.nextNode()) {
                        const text = walker.currentNode.textContent.trim();
                        const match = text.match(/^Rp\s*([\d.]+)$/);
                        if (!match) continue;
                        const numStr = match[1].replace(/\./g, '');
                        const num = parseInt(numStr, 10);
                        if (isNaN(num) || num < 100000) continue;
                        const el = walker.currentNode.parentElement;
                        if (!el) continue;
                        const style = window.getComputedStyle(el);
                        const fontSize = parseFloat(style.fontSize) || 12;
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            prices.push({ text, value: num, fontSize });
                        }
                    }
                    if (prices.length === 0) return null;
                    prices.sort((a, b) => b.fontSize - a.fontSize);
                    return prices[0].text;
                }
            """)
            if price_text:
                return self.parse_price(price_text)
        except Exception:
            logger.warning("DOM price extraction failed")

        return None
