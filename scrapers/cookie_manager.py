"""Shared cookie manager with encrypted storage.

Cookies are encrypted at rest using Fernet symmetric encryption.
The encryption key is derived from BOT_TOKEN (already a secret in .env).
This prevents credential exposure if the server filesystem is compromised.

Supported cookie format (Cookie-Editor export):
[
  {"name": "SPC_EC", "value": "...", "domain": ".shopee.co.id", ...},
  ...
]
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Valid platforms and their expected cookie domains
PLATFORMS = ("shopee", "tokopedia")

_PLATFORM_DOMAINS: dict[str, tuple[str, ...]] = {
    "shopee": (".shopee.co.id", "shopee.co.id"),
    "tokopedia": (".tokopedia.com", "tokopedia.com", ".www.tokopedia.com"),
}

# In-memory cookie cache: {platform: (mtime, cookies)}
_cache: dict[str, tuple[float, list[dict]]] = {}

# Max cookie file size (100KB)
_MAX_COOKIE_SIZE = 100 * 1024


def _get_cipher() -> Fernet:
    """Create Fernet cipher from BOT_TOKEN."""
    token = os.environ.get("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("BOT_TOKEN required for cookie encryption")
    # Derive a 32-byte key from the token
    key = hashlib.sha256(token.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _cookie_path(platform: str) -> Path:
    """Return the path to the encrypted cookie file."""
    return _DATA_DIR / f"{platform}_cookies.enc"


def _legacy_path(platform: str) -> Path:
    """Return the path to the old plaintext cookie file."""
    return _DATA_DIR / f"{platform}_cookies.json"


def _migrate_plaintext(platform: str) -> None:
    """Migrate plaintext cookie file to encrypted format."""
    legacy = _legacy_path(platform)
    if not legacy.exists():
        return
    encrypted = _cookie_path(platform)
    if encrypted.exists():
        # Already migrated — just delete the plaintext
        legacy.unlink()
        logger.info("Removed legacy plaintext cookie file: %s", legacy)
        return
    try:
        with open(legacy, "r", encoding="utf-8") as f:
            raw = f.read()
        # Validate it's valid JSON
        data = json.loads(raw)
        if isinstance(data, list):
            cipher = _get_cipher()
            encrypted_data = cipher.encrypt(raw.encode("utf-8"))
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(encrypted, "wb") as f:
                f.write(encrypted_data)
            legacy.unlink()
            logger.info("Migrated %s cookies from plaintext to encrypted", platform)
    except Exception:
        logger.exception("Failed to migrate plaintext cookies for %s", platform)


def has_cookies(platform: str) -> bool:
    """Check if cookies exist for the platform."""
    _migrate_plaintext(platform)
    return _cookie_path(platform).exists()


def load_cookies_raw(platform: str) -> list[dict]:
    """Load and decrypt cookie list. Returns [] if not found. Uses cache."""
    _migrate_plaintext(platform)
    path = _cookie_path(platform)
    if not path.exists():
        return []

    # Check cache by file modification time
    mtime = path.stat().st_mtime
    if platform in _cache and _cache[platform][0] == mtime:
        return _cache[platform][1]

    try:
        cipher = _get_cipher()
        with open(path, "rb") as f:
            encrypted_data = f.read()
        decrypted = cipher.decrypt(encrypted_data).decode("utf-8")
        data = json.loads(decrypted)
        if isinstance(data, list):
            _cache[platform] = (mtime, data)
            return data
        return []
    except InvalidToken:
        logger.error(
            "Cannot decrypt cookies for %s — BOT_TOKEN may have changed. "
            "Re-export cookies with /setcookies %s", platform, platform,
        )
        return []
    except Exception:
        logger.exception("Failed to load cookies for %s", platform)
        return []


def load_cookies_dict(platform: str) -> dict[str, str]:
    """Load cookies as {name: value} dict for httpx."""
    raw = load_cookies_raw(platform)
    return {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}


def load_cookies_playwright(platform: str) -> list[dict]:
    """Load cookies in Playwright format (for context.add_cookies)."""
    raw = load_cookies_raw(platform)
    pw_cookies = []
    for c in raw:
        if "name" not in c or "value" not in c:
            continue
        cookie: dict = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", f".{platform}.co.id"),
            "path": c.get("path", "/"),
        }
        if c.get("secure"):
            cookie["secure"] = True
        if c.get("httpOnly"):
            cookie["httpOnly"] = True
        pw_cookies.append(cookie)
    return pw_cookies


def save_cookies(platform: str, raw_json: str) -> tuple[bool, str]:
    """Validate, filter by domain, encrypt and save cookies.

    Returns (success, message).
    """
    if len(raw_json) > _MAX_COOKIE_SIZE:
        return False, f"Data terlalu besar (max {_MAX_COOKIE_SIZE // 1024}KB)"

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        return False, f"JSON tidak valid: {e}"

    if not isinstance(data, list):
        return False, "Format harus berupa JSON array [...]"

    if not data:
        return False, "Array cookies kosong"

    # Validate: each cookie must have name + value
    valid = [c for c in data if isinstance(c, dict) and "name" in c and "value" in c]
    if not valid:
        return False, "Tidak ditemukan cookie valid (harus punya 'name' dan 'value')"

    # Filter by domain: only accept cookies matching the platform
    allowed_domains = _PLATFORM_DOMAINS.get(platform, ())
    if allowed_domains:
        filtered = [
            c for c in valid
            if not c.get("domain") or c["domain"] in allowed_domains
        ]
        if not filtered:
            return False, (
                f"Tidak ada cookies yang cocok untuk {platform}. "
                f"Domain yang diterima: {', '.join(allowed_domains)}"
            )
        valid = filtered

    # Encrypt and save
    try:
        cipher = _get_cipher()
        json_str = json.dumps(valid, separators=(",", ":"))
        encrypted = cipher.encrypt(json_str.encode("utf-8"))

        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = _cookie_path(platform)
        with open(path, "wb") as f:
            f.write(encrypted)

        # Invalidate cache
        _cache.pop(platform, None)

        return True, f"Berhasil menyimpan {len(valid)} cookies untuk {platform} (terenkripsi)"
    except Exception as e:
        logger.exception("Failed to save cookies for %s", platform)
        return False, f"Gagal menyimpan: {e}"


def delete_cookies(platform: str) -> tuple[bool, str]:
    """Delete cookie file for a platform."""
    path = _cookie_path(platform)
    legacy = _legacy_path(platform)
    deleted = False

    if path.exists():
        path.unlink()
        deleted = True
    if legacy.exists():
        legacy.unlink()
        deleted = True

    _cache.pop(platform, None)

    if deleted:
        return True, f"Cookies {platform} berhasil dihapus"
    return False, f"Cookies {platform} tidak ditemukan"


def get_cookie_info(platform: str) -> dict:
    """Return info about cookies for a platform."""
    _migrate_plaintext(platform)
    path = _cookie_path(platform)
    if not path.exists():
        return {"exists": False, "count": 0, "modified": None}

    raw = load_cookies_raw(platform)
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return {
        "exists": True,
        "count": len(raw),
        "modified": modified.strftime("%Y-%m-%d %H:%M"),
        "encrypted": True,
    }
