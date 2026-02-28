"""Base scraper interface and shared utilities."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PriceResult:
    """Result of a price fetch operation."""
    price: int | None
    used_cookies: bool = False

    @property
    def source(self) -> str:
        """Return source label for DB storage."""
        return "cookies" if self.used_cookies else "no_cookies"


class BaseScraper(ABC):
    """Abstract base class for marketplace scrapers."""

    @abstractmethod
    async def fetch_price(self, url: str) -> PriceResult:
        """Fetch the current price for a product URL.

        Returns a PriceResult with the price (in Rupiah) and whether
        cookies were used for the request.
        """

    @staticmethod
    def parse_price(text: str) -> int | None:
        """Clean a price string and convert to integer.

        Handles formats like:
        - "Rp14.500.000"
        - "Rp 14.500.000"
        - "14500000"
        - "Rp14,500,000"

        Returns None if no digits found.
        """
        if not text:
            return None
        # Remove currency prefix, spaces, dots, commas
        cleaned = re.sub(r"[Rr][Pp]\s*", "", text)
        cleaned = re.sub(r"[\.\s,]", "", cleaned)
        # Extract digits only
        digits = re.sub(r"\D", "", cleaned)
        if not digits:
            return None
        return int(digits)
