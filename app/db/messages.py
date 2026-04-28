"""
db/messages.py
==============
Repository for raw_messages table (Bronze Layer).
Single responsibility: store and query unprocessed Telegram messages.
"""

import logging
from datetime import datetime, timezone, timedelta

from app.db.connection import _get_pool

logger = logging.getLogger(__name__)


async def insert_raw_message(
    message_id: str,
    channel: str,
    raw_text: str,
    received_at: datetime | str,
) -> bool:
    """
    Save a raw Telegram message to the bronze layer before any parsing.

    Returns True if inserted, False if it already existed (idempotent).
    """
    try:
        pool = _get_pool()
    except RuntimeError:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO raw_messages (message_id, channel, raw_text, received_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (message_id) DO NOTHING
                """,
                message_id,
                channel,
                raw_text,
                datetime.fromisoformat(received_at)
                if isinstance(received_at, str)
                else received_at,
            )
        return True
    except Exception as e:
        logger.error(f"Failed to insert raw message {message_id}: {e}")
        return False


async def get_unprocessed_messages(limit: int = 100) -> list[dict]:
    """
    Fetch raw messages that have not yet been parsed.
    Returns oldest-first so the parser processes in chronological order.
    """
    try:
        pool = _get_pool()
    except RuntimeError:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT message_id, channel, raw_text, received_at
            FROM raw_messages
            WHERE processed = FALSE
            ORDER BY received_at ASC
            LIMIT $1
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def mark_as_processed(message_id: str) -> None:
    """
    Mark a raw message as processed after the parser has handled it.
    Called whether parsing succeeded or the message was intentionally skipped.
    """
    try:
        pool = _get_pool()
    except RuntimeError:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE raw_messages SET processed = TRUE WHERE message_id = $1",
            message_id,
        )


async def get_raw_messages_count() -> dict:
    """Return counts of total and unprocessed raw messages. Used by /api/health."""
    try:
        pool = _get_pool()
    except RuntimeError:
        return {"total": 0, "unprocessed": 0}

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE processed = FALSE) AS unprocessed
            FROM raw_messages
            """
        )
    return {"total": row["total"], "unprocessed": row["unprocessed"]}


async def cleanup_old_raw_messages(days: int = 7) -> int:
    """
    Delete processed raw messages older than X days.
    Prevents the Bronze layer from growing infinitely with stale channel messages.
    """
    try:
        pool = _get_pool()
    except RuntimeError:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with pool.acquire() as conn:
        deleted = await conn.execute(
            """
            DELETE FROM raw_messages
            WHERE processed = TRUE
            AND received_at < $1
            """,
            cutoff,
        )
        try:
            count = int(deleted.split()[-1])
        except (ValueError, IndexError):
            count = 0

    if count > 0:
        logger.info(f"TTL Cleanup: deleted {count} old raw message(s)")

    return count
