"""
db/connection.py
================
Manages the asyncpg connection pool and database schema initialization.
Nothing else lives here — pure infrastructure.
"""

import logging
from datetime import datetime, timezone, timedelta

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

# Iraq timezone: UTC+3
IRAQ_TZ = timezone(timedelta(hours=3))

# ── Schema ────────────────────────────────────────────────────────────
SCHEMA_SQL = """
-- Bronze layer: every raw Telegram message, untouched, before any parsing
CREATE TABLE IF NOT EXISTS raw_messages (
    id           SERIAL PRIMARY KEY,
    message_id   TEXT     NOT NULL UNIQUE,  -- Telegram message ID (dedup key)
    channel      TEXT     NOT NULL,         -- e.g. @iraqborsa
    raw_text     TEXT     NOT NULL,         -- full message text, unmodified
    received_at  TIMESTAMPTZ NOT NULL,      -- UTC timestamp
    processed    BOOLEAN  NOT NULL DEFAULT FALSE  -- TRUE once parser has handled it
);

CREATE INDEX IF NOT EXISTS idx_raw_messages_processed
    ON raw_messages(processed);

CREATE INDEX IF NOT EXISTS idx_raw_messages_received_at
    ON raw_messages(received_at DESC);

-- Gold layer: validated, parsed Erbil exchange rates
CREATE TABLE IF NOT EXISTS exchange_rates (
    id                SERIAL PRIMARY KEY,
    erbil_penzi       INTEGER  NOT NULL CHECK (erbil_penzi > 0),
    erbil_sur         INTEGER  NOT NULL CHECK (erbil_sur > 0),
    erbil_average     INTEGER  NOT NULL CHECK (erbil_average > 0),
    source_message_id TEXT     NOT NULL UNIQUE,
    created_at        TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exchange_rates_created_at
    ON exchange_rates(created_at DESC);

-- Developer Portal: Users
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id  TEXT NOT NULL UNIQUE,
    email          TEXT NOT NULL UNIQUE,
    tier           TEXT NOT NULL DEFAULT 'free', -- free, pro, enterprise
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Developer Portal: API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash      TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL DEFAULT 'Default Key',
    masked_key    TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash
    ON api_keys(key_hash);
"""

# ── Connection Pool ───────────────────────────────────────────────────

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Initialize the database: create connection pool, create schema."""
    global _pool

    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL is not set in .env! Database connection will fail.")
        return

    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=1,
            max_size=10,
        )
        async with _pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)

        # Import here to avoid circular import at module level
        from app.db.rates import get_rates_count
        count = await get_rates_count()
        logger.info(f"PostgreSQL Database initialized ({count} records)")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db() -> None:
    """Close the database connection pool gracefully."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection closed")


def _get_pool() -> asyncpg.Pool:
    """Get the active database connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError(
            "Database connection pool not initialized. "
            "Make sure DATABASE_URL is set."
        )
    return _pool


def _now_iraq() -> datetime:
    """Return current UTC datetime (Postgres TIMESTAMPTZ handles timezones)."""
    return datetime.now(timezone.utc)
