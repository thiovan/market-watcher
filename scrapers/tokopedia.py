"""Tokopedia price scraper — Playwright + stealth with cookie support.

Uses shared browser singleton and playwright-stealth.
If cookies are available (set via /setcookies tokopedia), they're injected
for better reliability. Falls back to no-cookies if unavailable.
"""

from __future__ import annotations

import json
import logging
import re

from scrapers.base import BaseScraper, PriceResult
from scrapers.browser import create_stealth_context
from scrapers.cookie_manager import has_cookies, load_cookies_playwright
from scrapers.url_parser import extract_tokopedia_params

logger = logging.getLogger(__name__)


class TokopediaScraper(BaseScraper):
    """Fetch product price from Tokopedia using shared browser + stealth."""

    async def fetch_price(self, url: str) -> PriceResult:
        params = extract_tokopedia_params(url)
        if params is None:
            logger.warning("Cannot extract Tokopedia params from URL: %s", url)
            return PriceResult(price=None)

        # Try with cookies first (if available)
        if has_cookies("tokopedia"):
            result = await self._fetch(url, use_cookies=True)
            if result.price is not None:
                return result
            logger.info("Tokopedia fetch with cookies failed, trying without")

        return await self._fetch(url, use_cookies=False)

    async def _fetch(self, url: str, *, use_cookies: bool) -> PriceResult:
        """Load page via shared browser and extract price."""
        cookies = load_cookies_playwright("tokopedia") if use_cookies else []

        try:
            context, page = await create_stealth_context(cookies=cookies or None)

            try:
                mode = "cookies" if use_cookies and cookies else "no_cookies"
                logger.info("Loading Tokopedia [%s]: %s", mode, url[:80])

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Smart wait: look for price element instead of fixed sleep
                try:
                    await page.wait_for_function(
                        "() => document.body && document.body.innerText.includes('Rp')",
                        timeout=8000,
                    )
                except Exception:
                    pass  # Timeout OK — try extracting anyway

                price = await self._extract_price(page)

                if price:
                    used = use_cookies and bool(cookies)
                    logger.info("Tokopedia price [%s]: %d", mode, price)
                    return PriceResult(price=price, used_cookies=used)

                return PriceResult(price=None)

            finally:
                await context.close()

        except Exception:
            logger.exception("Tokopedia fetch failed for %s", url[:80])
            return PriceResult(price=None)

    async def _extract_price(self, page) -> int | None:
        """Extract price from rendered Tokopedia page."""
        # Strategy 1: Embedded JSON data in page source
        try:
            content = await page.content()
            price = self._extract_from_html(content)
            if price:
                return price
        except Exception:
            pass

        # Strategy 2: DOM text nodes
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
                        if (isNaN(num) || num < 1000) continue;
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
            pass

        return None

    def _extract_from_html(self, html: str) -> int | None:
        """Extract price from Tokopedia HTML using regex."""
        m = re.search(r'"price"\s*:\s*(\d{4,})', html)
        if m:
            return int(m.group(1))

        m = re.search(r'"priceFmt"\s*:\s*"(Rp[^"]+)"', html)
        if m:
            return self.parse_price(m.group(1))

        for key in ("discountedPrice", "slashedPrice", "originalPrice"):
            m = re.search(rf'"{key}"\s*:\s*"?(Rp[^",]+|[\d]+)"?', html)
            if m:
                price = self.parse_price(m.group(1)) if "Rp" in m.group(1) else int(m.group(1))
                if price and price > 100:
                    return price

        ld_matches = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        )
        for match in ld_matches:
            try:
                ld_data = json.loads(match.strip())
                items = ld_data if isinstance(ld_data, list) else [ld_data]
                for item in items:
                    if item.get("@type") == "Product":
                        offers = item.get("offers", {})
                        if isinstance(offers, list):
                            offers = offers[0] if offers else {}
                        p = offers.get("price") or offers.get("lowPrice")
                        if p:
                            return int(float(p))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        for pattern in (
            r'<meta[^>]*property="product:price:amount"[^>]*content="(\d+)"',
            r'<meta[^>]*content="(\d+)"[^>]*property="product:price:amount"',
        ):
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                return int(m.group(1))

        return None
