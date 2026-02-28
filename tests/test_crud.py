"""Tests for db.crud module using in-memory SQLite."""

import pytest

import db.crud as crud
from db.database import _db, close_db

# Override the database path to use in-memory SQLite for tests
import db.database as db_mod


@pytest.fixture(autouse=True)
async def setup_db():
    """Create an in-memory database for each test."""
    import aiosqlite
    from db.models import SCHEMA_SQL

    db_mod._db = await aiosqlite.connect(":memory:")
    db_mod._db.row_factory = aiosqlite.Row
    await db_mod._db.execute("PRAGMA foreign_keys=ON")
    await db_mod._db.executescript(SCHEMA_SQL)
    await db_mod._db.commit()
    yield
    await db_mod._db.close()
    db_mod._db = None


class TestProducts:
    async def test_add_and_get(self):
        pid = await crud.add_product("iPhone 16", 12345)
        assert pid > 0
        products = await crud.get_products_by_user(12345)
        assert len(products) == 1
        assert products[0]["name"] == "iPhone 16"

    async def test_delete(self):
        pid = await crud.add_product("Test", 12345)
        await crud.delete_product(pid)
        products = await crud.get_products_by_user(12345)
        assert len(products) == 0

    async def test_update_interval(self):
        pid = await crud.add_product("Test", 12345)
        await crud.update_product_interval(pid, 60)
        products = await crud.get_products_by_user(12345)
        assert products[0]["check_interval_minutes"] == 60


class TestProductLinks:
    async def test_add_and_get(self):
        pid = await crud.add_product("Test", 12345)
        lid = await crud.add_product_link(pid, "https://tokopedia.com/s/p", "tokopedia")
        assert lid > 0
        links = await crud.get_links_by_product(pid)
        assert len(links) == 1
        assert links[0]["platform"] == "tokopedia"

    async def test_cascade_delete(self):
        pid = await crud.add_product("Test", 12345)
        await crud.add_product_link(pid, "https://example.com", "unknown")
        await crud.delete_product(pid)
        links = await crud.get_links_by_product(pid)
        assert len(links) == 0


class TestPriceHistory:
    async def test_record_and_get(self):
        pid = await crud.add_product("Test", 12345)
        lid = await crud.add_product_link(pid, "https://example.com", "unknown")
        await crud.record_price(lid, 15000000)
        await crud.record_price(lid, 14500000)
        history = await crud.get_price_history(lid)
        assert len(history) == 2

    async def test_lowest_price(self):
        pid = await crud.add_product("Test", 12345)
        lid = await crud.add_product_link(pid, "https://example.com", "unknown")
        await crud.record_price(lid, 15000000)
        await crud.record_price(lid, 14000000)
        await crud.record_price(lid, 14500000)
        lowest = await crud.get_lowest_price(lid)
        assert lowest == 14000000

    async def test_last_price(self):
        pid = await crud.add_product("Test", 12345)
        lid = await crud.add_product_link(pid, "https://example.com", "unknown")
        await crud.record_price(lid, 15000000)
        await crud.record_price(lid, 14500000)
        last = await crud.get_last_price(lid)
        assert last == 14500000


class TestAlertRules:
    async def test_add_and_get(self):
        pid = await crud.add_product("Test", 12345)
        rid = await crud.add_alert_rule(pid, "PRICE_DROP")
        assert rid > 0
        alerts = await crud.get_alerts_by_product(pid)
        assert len(alerts) == 1
        assert alerts[0]["rule_type"] == "PRICE_DROP"

    async def test_target_price_rule(self):
        pid = await crud.add_product("Test", 12345)
        await crud.add_alert_rule(pid, "TARGET_PRICE", 14000000)
        alerts = await crud.get_alerts_by_product(pid)
        assert alerts[0]["target_value"] == 14000000

    async def test_delete_rule(self):
        pid = await crud.add_product("Test", 12345)
        rid = await crud.add_alert_rule(pid, "HISTORICAL_LOW")
        await crud.delete_alert_rule(rid)
        alerts = await crud.get_alerts_by_product(pid)
        assert len(alerts) == 0
