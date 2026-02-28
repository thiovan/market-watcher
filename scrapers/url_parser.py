"""URL parsing utilities to detect marketplace platform and extract parameters."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def detect_platform(url: str) -> str:
    """Detect the marketplace platform from a URL.

    Returns one of: 'tokopedia', 'shopee', or 'unknown'.
    """
    host = urlparse(url).hostname or ""
    host = host.lower()
    if "tokopedia.com" in host:
        return "tokopedia"
    if "shopee.co.id" in host or "shopee.com" in host:
        return "shopee"
    return "unknown"


def extract_tokopedia_params(url: str) -> tuple[str, str] | None:
    """Extract (shop_domain, product_key) from a Tokopedia product URL.

    Expected URL format: https://www.tokopedia.com/{shop_domain}/{product_key}
    Returns None if the URL doesn't match.
    """
    parsed = urlparse(url)
    # Remove query string and fragment, split path
    path = parsed.path.strip("/")
    parts = path.split("/")
    # Filter out empty parts and known non-product prefixes
    if len(parts) >= 2 and parts[0] not in ("promo", "discovery", "search", "p"):
        return parts[0], parts[1]
    return None


def extract_shopee_params(url: str) -> tuple[int, int] | None:
    """Extract (shop_id, item_id) from a Shopee product URL.

    Supported formats:
    - https://shopee.co.id/product-name-i.{shop_id}.{item_id}
    - https://shopee.co.id/product/{shop_id}/{item_id}
    Returns None if extraction fails.
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    # Format: /product-name-i.SHOPID.ITEMID
    match = re.search(r"-i\.(\d+)\.(\d+)", path)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Format: /product/SHOPID/ITEMID
    match = re.search(r"product/(\d+)/(\d+)", path)
    if match:
        return int(match.group(1)), int(match.group(2))

    return None
