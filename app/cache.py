"""
Redis Cache Module
==================
Manages the Redis connection and provides a typed interface for
caching the latest exchange rate.

Responsibilities:
  - init/close the Redis connection (called from app/main.py lifespan)
  - set_latest_rate()  → serialize rate to JSON, store in Redis with TTL
  - get_latest_rate()  → read from Redis; returns None if missing or Redis down
  - delete_latest_rate() → used for cleanup / testing

Design:
  - All Redis failures are caught and logged — Redis being down must NEVER
    crash the API. The API falls back to PostgreSQL automatically.
  - TTL is set to 10 minutes (600s). If Redis restarts, the next API call
    falls back to PostgreSQL and re-populates the cache.
  - Phase 3 NOTE: This module is intentionally simple. Rate limiting for
    API keys (Phase 3b) will be added as a separate function here.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Redis Key Constants ───────────────────────────────────────────────

RATE_KEY = "rate:latest"           # Key for the cached latest rate
EVENT_KEY = "event:last_received"  # Key for tracking the last event listener hit
WS_CHANNEL = "ws:broadcast"        # Channel for broadcasting websocket updates
RATE_TTL = 600                     # 10 minutes — cache lifetime in seconds

# ── Connection Pool ───────────────────────────────────────────────────

_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    """
    Initialize the Redis connection pool.
    Called during FastAPI startup (lifespan).
    Logs a warning if Redis is unreachable — does NOT raise.
    """
    global _redis
    try:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,   # fail fast if Redis is unreachable
            socket_timeout=3,
        )
        # Ping to verify the connection is alive at startup
        await _redis.ping()
        logger.info(f"Redis connected: {settings.REDIS_URL}")
    except Exception as e:
        logger.warning(
            f"Redis unavailable at startup: {e} — "
            "API will fall back to PostgreSQL for rate reads. "
            "Cache will be populated once Redis becomes reachable."
        )
        _redis = None


async def close_redis() -> None:
    """Close the Redis connection pool. Called during FastAPI shutdown."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


def _get_redis() -> aioredis.Redis | None:
    """Return the active Redis client, or None if not connected."""
    return _redis


# ── Cache Operations ──────────────────────────────────────────────────

async def set_latest_rate(rate: dict[str, Any]) -> bool:
    """
    Store the latest rate in Redis as JSON.

    Args:
        rate: Dict with keys: city, penzi, sur, average, daily_change, last_updated

    Returns:
        True if stored successfully, False if Redis is unavailable.
    """
    client = _get_redis()
    if client is None:
        return False

    try:
        payload = json.dumps(rate, ensure_ascii=False, default=str)
        await client.set(RATE_KEY, payload, ex=RATE_TTL)
        logger.debug(f"Redis cache updated: avg={rate.get('average', '?')}")
        return True
    except Exception as e:
        logger.warning(f"Redis set failed: {e}")
        return False


async def get_latest_rate() -> dict[str, Any] | None:
    """
    Read the latest rate from Redis.

    Returns:
        Rate dict if found and valid JSON, None otherwise.
        Never raises — caller must handle None (fallback to PostgreSQL).
    """
    client = _get_redis()
    if client is None:
        return None

    try:
        raw = await client.get(RATE_KEY)
        if raw is None:
            return None  # TTL expired or not yet set
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Redis get failed: {e}")
        return None


async def delete_latest_rate() -> None:
    """
    Remove the cached rate from Redis.
    Used in tests or when you want to force a fresh DB read.
    """
    client = _get_redis()
    if client is None:
        return

    try:
        await client.delete(RATE_KEY)
        logger.debug("Redis cache cleared")
    except Exception as e:
        logger.warning(f"Redis delete failed: {e}")


async def is_redis_healthy() -> bool:
    """
    Check if Redis is reachable. Used by /api/health endpoint.
    Returns True if ping succeeds, False otherwise.
    """
    client = _get_redis()
    if client is None:
        return False

    try:
        await client.ping()
        return True
    except Exception:
        return False

# ── Event Observability ───────────────────────────────────────────────

async def set_last_event_time(timestamp_iso: str) -> None:
    """Store the ISO timestamp of the last message received via the event listener."""
    client = _get_redis()
    if client:
        try:
            await client.set(EVENT_KEY, timestamp_iso)
        except Exception:
            pass

async def get_last_event_time() -> str | None:
    """Get the ISO timestamp of the last message received via the event listener."""
    client = _get_redis()
    if client:
        try:
            return await client.get(EVENT_KEY)
        except Exception:
            pass
    return None

# ── Pub/Sub for WebSockets ────────────────────────────────────────────

async def publish_new_rate(rate_payload: dict[str, Any]) -> None:
    """Publish a new rate payload to the Redis channel for WebSocket broadcasting."""
    client = _get_redis()
    if client:
        try:
            payload = json.dumps(rate_payload, ensure_ascii=False, default=str)
            await client.publish(WS_CHANNEL, payload)
        except Exception as e:
            logger.warning(f"Redis publish failed: {e}")

async def listen_for_rates(callback) -> None:
    """
    Listen for new rate payloads on the Redis channel and trigger the callback.

    Uses a DEDICATED connection separate from the main read/write pool.
    Pub/Sub blocks the connection — sharing it would starve all other Redis calls.

    Auto-reconnects with exponential backoff if Upstash drops the idle connection
    (Upstash serverless has a ~60s idle timeout on persistent TCP connections).
    """
    import asyncio

    if not settings.REDIS_URL:
        logger.warning("Redis URL not set. WebSocket Pub/Sub disabled.")
        return

    retry_delay = 2   # seconds — starts low, grows on repeated failures
    MAX_DELAY    = 60 # cap at 60s between reconnection attempts

    # Reconnect alerting: track failures in a rolling 10-minute window
    import time
    ALERT_WINDOW    = 600   # 10 minutes in seconds
    ALERT_THRESHOLD = 3     # escalate to ERROR after this many reconnects
    reconnect_times: list[float] = []

    while True:
        pubsub = None
        dedicated_client = None
        try:
            # ── Dedicated connection for Pub/Sub ──────────────────────
            # Longer socket_timeout than the main pool: we WANT to block
            # waiting for messages, but not forever — 30s lets us detect
            # a dead connection and reconnect cleanly.
            dedicated_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=30,
            )

            pubsub = dedicated_client.pubsub()
            await pubsub.subscribe(WS_CHANNEL)
            logger.info(f"Pub/Sub: subscribed to channel '{WS_CHANNEL}'")

            retry_delay = 2  # reset backoff on successful connection

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        await callback(payload)
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"Pub/Sub: bad message payload: {e}")

        except asyncio.CancelledError:
            logger.info("Pub/Sub: listener cancelled — shutting down")
            break  # Clean shutdown — do not retry

        except Exception as e:
            now = time.time()

            # Prune events outside the rolling window
            reconnect_times.append(now)
            reconnect_times[:] = [t for t in reconnect_times if now - t <= ALERT_WINDOW]

            recent = len(reconnect_times)
            if recent >= ALERT_THRESHOLD:
                logger.error(
                    f"Pub/Sub: {recent} reconnects in the last "
                    f"{ALERT_WINDOW // 60} minutes — possible persistent "
                    f"connectivity issue. Last error: {e}"
                )
            else:
                logger.warning(
                    f"Pub/Sub: connection lost ({e}). "
                    f"Reconnecting in {retry_delay}s "
                    f"(reconnect {recent}/{ALERT_THRESHOLD} in window)..."
                )

            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, MAX_DELAY)  # exponential backoff

        finally:
            # Always clean up the dedicated connection on exit or error
            if pubsub:
                try:
                    await pubsub.unsubscribe(WS_CHANNEL)
                    await pubsub.aclose()
                except Exception:
                    pass
            if dedicated_client:
                try:
                    await dedicated_client.aclose()
                except Exception:
                    pass

