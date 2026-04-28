"""
db/rates.py
===========
Repository for exchange_rates table.
Single responsibility: read and write Erbil exchange rate records.
"""

import logging
from datetime import datetime, timezone, timedelta

import asyncpg

from app.db.connection import _get_pool, _now_iraq, IRAQ_TZ

logger = logging.getLogger(__name__)


async def insert_rate(
    penzi: int,
    sur: int,
    average: int,
    message_id: str,
    created_at: datetime | str | None = None,
) -> int | None:
    """
    Insert a new exchange rate record.

    Returns the row ID if successful, None if the message was already stored
    (duplicate source_message_id — idempotent by design).
    """
    try:
        pool = _get_pool()
    except RuntimeError:
        return None

    if isinstance(created_at, str):
        timestamp = datetime.fromisoformat(created_at)
    else:
        timestamp = created_at if created_at else _now_iraq()

    try:
        async with pool.acquire() as conn:
            row_id = await conn.fetchval(
                """
                INSERT INTO exchange_rates (erbil_penzi, erbil_sur, erbil_average, source_message_id, created_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                penzi, sur, average, message_id, timestamp
            )
        logger.info(f"Stored rate: penzi={penzi}, sur={sur}, avg={average}, msg_id={message_id}")
        return row_id
    except asyncpg.exceptions.UniqueViolationError:
        logger.debug(f"Duplicate message ID skipped: {message_id}")
        return None


async def get_latest_rate() -> dict | None:
    """Return the most recently stored exchange rate."""
    try:
        pool = _get_pool()
    except RuntimeError:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM exchange_rates ORDER BY id DESC LIMIT 1"
        )
    return dict(row) if row else None


async def get_rate_24h_ago() -> dict | None:
    """
    Return the last rate from before today midnight (Iraq time).
    Used to calculate the daily change figure shown on the frontend.
    """
    try:
        pool = _get_pool()
    except RuntimeError:
        return None

    today_midnight = datetime.now(IRAQ_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM exchange_rates WHERE created_at < $1 ORDER BY created_at DESC LIMIT 1",
            today_midnight,
        )
        if not row:
            row = await conn.fetchrow(
                "SELECT * FROM exchange_rates ORDER BY created_at ASC LIMIT 1"
            )

    return dict(row) if row else None


async def get_last_stored_average() -> int | None:
    """Convenience wrapper: return just the erbil_average from the latest row."""
    rate = await get_latest_rate()
    return rate["erbil_average"] if rate else None


async def get_last_message_id() -> str | None:
    """Return the source_message_id of the most recently stored rate."""
    try:
        pool = _get_pool()
    except RuntimeError:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT source_message_id FROM exchange_rates ORDER BY id DESC LIMIT 1"
        )
    return row["source_message_id"] if row else None


async def get_rate_history(days: int = 7) -> list[dict]:
    """
    Return aggregated historical rates.
    - ≤7 days  → hourly granularity
    - >7 days  → daily granularity
    """
    try:
        pool = _get_pool()
    except RuntimeError:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with pool.acquire() as conn:
        if days <= 7:
            rows = await conn.fetch(
                """
                SELECT
                    date_trunc('hour', created_at AT TIME ZONE 'UTC-3') as trunc_date,
                    CAST(ROUND(AVG(erbil_penzi)) AS INTEGER) as penzi,
                    CAST(ROUND(AVG(erbil_sur)) AS INTEGER) as sur,
                    CAST(ROUND(AVG(erbil_average)) AS INTEGER) as average
                FROM exchange_rates
                WHERE created_at >= $1
                GROUP BY date_trunc('hour', created_at AT TIME ZONE 'UTC-3')
                ORDER BY trunc_date DESC
                """,
                cutoff,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    date_trunc('day', created_at AT TIME ZONE 'UTC-3') as trunc_date,
                    CAST(ROUND(AVG(erbil_penzi)) AS INTEGER) as penzi,
                    CAST(ROUND(AVG(erbil_sur)) AS INTEGER) as sur,
                    CAST(ROUND(AVG(erbil_average)) AS INTEGER) as average
                FROM exchange_rates
                WHERE created_at >= $1
                GROUP BY date_trunc('day', created_at AT TIME ZONE 'UTC-3')
                ORDER BY trunc_date DESC
                """,
                cutoff,
            )

    results = []
    for row in rows:
        r = dict(row)
        naive_dt = r.pop("trunc_date")
        r["last_updated"] = naive_dt.replace(tzinfo=IRAQ_TZ)
        results.append(r)

    return results


async def get_rates_count() -> int:
    """Return the total number of stored exchange rate records."""
    try:
        pool = _get_pool()
    except RuntimeError:
        return 0

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM exchange_rates")
    return row["cnt"] if row else 0
