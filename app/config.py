"""
Configuration & Constants Module
================================
Single source of truth for all settings, keywords, and thresholds.
Loads secrets from .env file, defines all parser keywords as constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Project Paths ─────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "rates.db"

# ── Load .env ─────────────────────────────────────────────────────────
load_dotenv(ENV_PATH)


class Settings:
    """Application settings loaded from environment variables and defaults."""

    # ── Telegram Credentials (from .env) ──────────────────────────────
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_PHONE: str = os.getenv("TELEGRAM_PHONE", "")
    TELEGRAM_CHANNEL: str = os.getenv("TELEGRAM_CHANNEL", "@iraqborsa")

    # ── Session ───────────────────────────────────────────────────────
    TELEGRAM_SESSION_STRING: str = os.getenv("TELEGRAM_SESSION_STRING", "")

    # ── Trusted Sender IDs ────────────────────────────────────────────
    # Comma-separated Telegram user/bot IDs whose messages are processed.
    # Messages from other senders are stored in Bronze but NOT parsed.
    # Empty string = disabled (all senders trusted) — set in production!
    # Find a sender ID by printing msg.sender_id in the event handler.
    TELEGRAM_TRUSTED_SENDER_IDS_RAW: str = os.getenv(
        "TELEGRAM_TRUSTED_SENDER_IDS", ""
    )

    @property
    def TELEGRAM_TRUSTED_SENDER_IDS(self) -> set:
        """Returns the parsed set of trusted sender IDs. Empty = all trusted."""
        if not self.TELEGRAM_TRUSTED_SENDER_IDS_RAW.strip():
            return set()
        ids = set()
        for part in self.TELEGRAM_TRUSTED_SENDER_IDS_RAW.split(","):
            part = part.strip()
            try:
                ids.add(int(part))  # handles both positive and negative IDs
            except ValueError:
                pass  # silently skip malformed entries
        return ids

    # ── Scheduler ─────────────────────────────────────────────────────
    FETCH_INTERVAL_SECONDS: int = 300  # 5 minutes

    # ── Database ──────────────────────────────────────────────────────
    DB_PATH: Path = DB_PATH
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # ── Redis ─────────────────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── Clerk Authentication ──────────────────────────────────────────
    # Your Clerk Frontend API URL — found in the Clerk dashboard under
    # API Keys → Advanced → Frontend API URL
    # e.g. https://fast-midge-51.clerk.accounts.dev
    CLERK_FRONTEND_API_URL: str = os.getenv("CLERK_FRONTEND_API_URL", "")

    # JWKS cache TTL in Redis: 1 hour (Clerk rotates keys rarely)
    CLERK_JWKS_CACHE_TTL: int = 3600

    # ── CORS ─────────────────────────────────────────────────────────
    # Comma-separated list of allowed CORS origins.
    # Defaults to local dev origins. Override in production .env.
    # Example: ALLOWED_ORIGINS=https://iqdrate.com,https://www.iqdrate.com
    ALLOWED_ORIGINS_RAW: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5500"
    )

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        """Returns the parsed list of allowed CORS origins."""
        return [o.strip() for o in self.ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

    # ── Parser: City Keywords ─────────────────────────────────────────
    # Lines must contain at least one of these to be considered Erbil
    CITY_KEYWORDS: list[str] = ["هەولێر"]

    # ── Parser: Rate Type Keywords ────────────────────────────────────
    PENZI_KEYWORDS: list[str] = ["پێنجی"]
    SUR_KEYWORDS: list[str] = ["سوور"]
    KRIN_KEYWORDS: list[str] = ["کڕین"]
    FROSHTN_KEYWORDS: list[str] = ["فرۆشتن"]

    # ── Parser: Exclusion Keywords (skip entire message) ──────────────
    # Gold, official rate, central bank
    EXCLUDE_KEYWORDS: list[str] = [
        "ذهب",           # Arabic: gold
        "زێر",           # Kurdish: gold
        "الذهب",          # Arabic: the gold
    ]

    # ── Parser: Validation ────────────────────────────────────────────
    MIN_VALID_PRICE: int = 100_000   # Minimum valid IQD per 100 USD
    MAX_VALID_PRICE: int = 200_000   # Maximum valid IQD per 100 USD
    MAX_ANOMALY_DEVIATION: int = 10_000  # Max allowed change from last rate

    # ── Backfill ──────────────────────────────────────────────────────
    INITIAL_FETCH_COUNT: int = 1500  # Messages to fetch on first run

    # ── Timezone ──────────────────────────────────────────────────────
    TIMEZONE: str = "Asia/Baghdad"  # UTC+3, Iraq time

    def validate(self) -> list[str]:
        """Check that required settings are present. Returns list of errors."""
        errors = []
        if self.TELEGRAM_API_ID == 0:
            errors.append("TELEGRAM_API_ID is not set in .env")
        if not self.TELEGRAM_API_HASH:
            errors.append("TELEGRAM_API_HASH is not set in .env")
        if not self.TELEGRAM_SESSION_STRING:
            errors.append("TELEGRAM_SESSION_STRING is not set in .env")
        return errors


# ── Singleton instance ────────────────────────────────────────────────
settings = Settings()
