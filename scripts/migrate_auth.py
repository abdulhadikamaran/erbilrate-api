"""
Database Migration: Clerk Auth & API Key Hashing
================================================
This script creates the users and api_keys tables according to Phase 8 specifications.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("migrate_clerk")

async def migrate():
    await db.init_db()
    pool = db._get_pool()
    
    logger.info("Starting Clerk Auth & API Key migration...")
    
    try:
        async with pool.acquire() as conn:
            # We use IF NOT EXISTS to be safe, but if you ran the previous script,
            # you might need to DROP TABLE api_keys, users; first if you want a clean slate.
            
            logger.info("Creating users table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    clerk_user_id  TEXT NOT NULL UNIQUE,
                    email          TEXT NOT NULL UNIQUE,
                    tier           TEXT NOT NULL DEFAULT 'free',
                    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            logger.info("Creating api_keys table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    key_hash      TEXT NOT NULL UNIQUE,
                    name          TEXT NOT NULL DEFAULT 'Default Key',
                    masked_key    TEXT NOT NULL,
                    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            logger.info("Creating indexes...")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash
                    ON api_keys(key_hash);
            """)
            
            logger.info("Clerk Auth migration complete.")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    finally:
        await db.close_db()

if __name__ == "__main__":
    asyncio.run(migrate())
