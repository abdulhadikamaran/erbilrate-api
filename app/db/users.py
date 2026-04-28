"""
db/users.py
===========
Repository for users and api_keys tables.
Single responsibility: user identity, API key lifecycle, and billing queries.

Note: Key generation helpers (hashing, masking) remain in app/auth.py.
      This module only handles the database operations they require.
"""

import logging

from app.db.connection import _get_pool

logger = logging.getLogger(__name__)


async def get_or_create_user(
    clerk_user_id: str,
    email: str,
    tier: str = "free",
) -> str | None:
    """
    Finds a user by Clerk ID, or creates them on first login.
    Returns the PostgreSQL user UUID as a string.
    """
    try:
        pool = _get_pool()
        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "SELECT id FROM users WHERE clerk_user_id = $1",
                clerk_user_id,
            )
            if user_id:
                return str(user_id)

            user_id = await conn.fetchval(
                """
                INSERT INTO users (clerk_user_id, email, tier)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                clerk_user_id,
                email,
                tier,
            )
            return str(user_id)
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        return None


async def create_api_key_for_user(
    user_id: str,
    key_hash: str,
    masked_key: str,
    name: str = "Default Key",
) -> str | None:
    """
    Persists a pre-generated API key to the database.
    Returns the new key UUID, or None on failure.

    Raw key generation and hashing happen in app/auth.py before calling here.
    """
    try:
        pool = _get_pool()
        async with pool.acquire() as conn:
            key_id = await conn.fetchval(
                """
                INSERT INTO api_keys (user_id, key_hash, name, masked_key)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_id,
                key_hash,
                name,
                masked_key,
            )
            return str(key_id) if key_id else None
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        return None


async def validate_api_key(raw_api_key: str) -> dict | None:
    """
    Authenticate an API request by hashing the incoming key and checking the DB.
    Returns user dict {user_id, email, tier} or None if invalid/revoked.
    """
    import hashlib
    key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()

    try:
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.id as user_id, u.email, u.tier
                FROM api_keys a
                JOIN users u ON a.user_id = u.id
                WHERE a.key_hash = $1 AND a.is_active = TRUE
                """,
                key_hash,
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        return None


async def list_user_keys(user_id: str) -> list[dict]:
    """Return all active keys for a user (masked versions only — never raw)."""
    try:
        pool = _get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, masked_key, created_at
                FROM api_keys
                WHERE user_id = $1 AND is_active = TRUE
                ORDER BY created_at DESC
                """,
                user_id,
            )
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        return []


async def revoke_api_key(key_id: str, user_id: str) -> bool:
    """
    Soft-delete an API key by marking it inactive.
    Validates ownership (user_id) before revoking to prevent cross-user attacks.
    """
    try:
        pool = _get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE api_keys
                SET is_active = FALSE
                WHERE id = $1 AND user_id = $2
                """,
                key_id,
                user_id,
            )
            return result == "UPDATE 1"
    except Exception as e:
        logger.error(f"Error revoking API key: {e}")
        return False
