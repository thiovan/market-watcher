"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    bot_token: str = field(repr=False, default="")
    admin_user_id: int = 0
    check_interval_minutes: int = 240
    database_path: str = "data/market_watcher.db"

    # Scraping settings
    request_delay_seconds: float = 10.0
    batch_delay_seconds: float = 30.0
    max_links_per_cycle: int = 20
    headless: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        """Create settings from environment variables."""
        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            admin_user_id=int(os.getenv("ADMIN_USER_ID", "0")),
            check_interval_minutes=int(os.getenv("CHECK_INTERVAL_MINUTES", "240")),
            database_path=os.getenv("DATABASE_PATH", "data/market_watcher.db"),
            headless=os.getenv("HEADLESS", "false").lower() != "false",
            request_delay_seconds=float(os.getenv("SCRAPE_DELAY_SECONDS", "10")),
            batch_delay_seconds=float(os.getenv("SCRAPE_BATCH_DELAY_SECONDS", "30")),
        )

    def validate(self) -> None:
        """Raise if critical settings are missing."""
        if not self.bot_token:
            raise ValueError("BOT_TOKEN is required. Set it in .env file.")
        if not self.admin_user_id:
            raise ValueError("ADMIN_USER_ID is required. Set it in .env file.")

    @property
    def db_path(self) -> Path:
        """Return database path as Path object, creating parent dirs."""
        p = Path(self.database_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings.from_env()
