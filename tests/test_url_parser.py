"""Tests for scrapers.url_parser module."""

from scrapers.url_parser import (
    detect_platform,
    extract_shopee_params,
    extract_tokopedia_params,
)


class TestDetectPlatform:
    def test_tokopedia(self):
        assert detect_platform("https://www.tokopedia.com/shop/product") == "tokopedia"

    def test_tokopedia_mobile(self):
        assert detect_platform("https://m.tokopedia.com/shop/product") == "tokopedia"

    def test_shopee_co_id(self):
        assert detect_platform("https://shopee.co.id/product-i.123.456") == "shopee"

    def test_shopee_com(self):
        assert detect_platform("https://shopee.com/product-i.123.456") == "shopee"

    def test_unknown(self):
        assert detect_platform("https://bukalapak.com/p/something") == "unknown"

    def test_invalid(self):
        assert detect_platform("not-a-url") == "unknown"


class TestExtractTokopediaParams:
    def test_standard_url(self):
        url = "https://www.tokopedia.com/myshop/iphone-16-pro-max"
        result = extract_tokopedia_params(url)
        assert result == ("myshop", "iphone-16-pro-max")

    def test_url_with_query(self):
        url = "https://www.tokopedia.com/myshop/product-xyz?src=topads"
        result = extract_tokopedia_params(url)
        assert result == ("myshop", "product-xyz")

    def test_promo_url_returns_none(self):
        url = "https://www.tokopedia.com/promo/something"
        result = extract_tokopedia_params(url)
        assert result is None

    def test_short_path_returns_none(self):
        url = "https://www.tokopedia.com/onlyshop"
        result = extract_tokopedia_params(url)
        assert result is None


class TestExtractShopeeParams:
    def test_standard_url(self):
        url = "https://shopee.co.id/Product-Name-i.123456.789012"
        result = extract_shopee_params(url)
        assert result == (123456, 789012)

    def test_product_path_format(self):
        url = "https://shopee.co.id/product/123456/789012"
        result = extract_shopee_params(url)
        assert result == (123456, 789012)

    def test_invalid_url(self):
        url = "https://shopee.co.id/something-random"
        result = extract_shopee_params(url)
        assert result is None
