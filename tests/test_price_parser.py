"""Tests for scrapers.base price parsing."""

from scrapers.base import BaseScraper


class TestParsePrice:
    """Test the static parse_price method."""

    def test_standard_format(self):
        assert BaseScraper.parse_price("Rp14.500.000") == 14500000

    def test_with_space(self):
        assert BaseScraper.parse_price("Rp 14.500.000") == 14500000

    def test_no_prefix(self):
        assert BaseScraper.parse_price("14500000") == 14500000

    def test_with_commas(self):
        assert BaseScraper.parse_price("Rp14,500,000") == 14500000

    def test_lowercase_rp(self):
        assert BaseScraper.parse_price("rp14.500.000") == 14500000

    def test_empty_string(self):
        assert BaseScraper.parse_price("") is None

    def test_no_digits(self):
        assert BaseScraper.parse_price("Rp") is None

    def test_small_price(self):
        assert BaseScraper.parse_price("Rp50.000") == 50000

    def test_mixed_separators(self):
        assert BaseScraper.parse_price("Rp 1.234.567") == 1234567
