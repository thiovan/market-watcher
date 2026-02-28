"""SQL DDL statements for the database schema."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    user_telegram_id  INTEGER NOT NULL,
    check_interval_minutes INTEGER NOT NULL DEFAULT 15,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS product_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    url         TEXT    NOT NULL,
    platform    TEXT    NOT NULL DEFAULT 'unknown',
    selector    TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    last_checked TEXT,
    last_price  INTEGER,
    fail_count  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id     INTEGER NOT NULL REFERENCES product_links(id) ON DELETE CASCADE,
    price       INTEGER NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'no_cookies',
    checked_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    rule_type   TEXT    NOT NULL CHECK(rule_type IN ('PRICE_DROP','TARGET_PRICE','HISTORICAL_LOW')),
    target_value INTEGER
);

CREATE INDEX IF NOT EXISTS idx_product_links_product ON product_links(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_link    ON price_history(link_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_product   ON alert_rules(product_id);
CREATE INDEX IF NOT EXISTS idx_products_user         ON products(user_telegram_id);
"""
