"""
Database Migration: TEXT to TIMESTAMPTZ
=======================================
This script alters the existing tables to convert TEXT timestamp columns
into native PostgreSQL TIMESTAMPTZ columns.
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
logger = logging.getLogger("migrate")

async def migrate():
    await db.init_db()
    pool = db._get_pool()
    
    logger.info("Starting migration to TIMESTAMPTZ...")
    
    try:
        async with pool.acquire() as conn:
            # 1. Migrate raw_messages
            logger.info("Migrating raw_messages.received_at...")
            await conn.execute("""
                ALTER TABLE raw_messages 
                ALTER COLUMN received_at TYPE TIMESTAMPTZ 
                USING received_at::timestamptz
            """)
            logger.info("raw_messages migration complete.")
            
            # 2. Migrate exchange_rates
            logger.info("Migrating exchange_rates.created_at...")
            await conn.execute("""
                ALTER TABLE exchange_rates 
                ALTER COLUMN created_at TYPE TIMESTAMPTZ 
                USING created_at::timestamptz
            """)
            logger.info("exchange_rates migration complete.")
            
        logger.info("All migrations completed successfully!")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    finally:
        await db.close_db()

if __name__ == "__main__":
    asyncio.run(migrate())
