"""
Migration: Add CHECK constraints to exchange_rates table.
Safe to run multiple times — uses DO $$ IF NOT EXISTS $$ blocks.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def migrate():
    url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(dsn=url)

    migrations = [
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_penzi_positive'
                  AND conrelid = 'exchange_rates'::regclass
            ) THEN
                ALTER TABLE exchange_rates
                    ADD CONSTRAINT chk_penzi_positive CHECK (erbil_penzi > 0);
                RAISE NOTICE 'Added chk_penzi_positive';
            ELSE
                RAISE NOTICE 'chk_penzi_positive already exists — skipped';
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_sur_positive'
                  AND conrelid = 'exchange_rates'::regclass
            ) THEN
                ALTER TABLE exchange_rates
                    ADD CONSTRAINT chk_sur_positive CHECK (erbil_sur > 0);
                RAISE NOTICE 'Added chk_sur_positive';
            ELSE
                RAISE NOTICE 'chk_sur_positive already exists — skipped';
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_average_positive'
                  AND conrelid = 'exchange_rates'::regclass
            ) THEN
                ALTER TABLE exchange_rates
                    ADD CONSTRAINT chk_average_positive CHECK (erbil_average > 0);
                RAISE NOTICE 'Added chk_average_positive';
            ELSE
                RAISE NOTICE 'chk_average_positive already exists — skipped';
            END IF;
        END $$;
        """,
    ]

    print("Running migrations...")
    for sql in migrations:
        await conn.execute(sql)

    # Verify
    rows = await conn.fetch(
        """
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'exchange_rates'::regclass
          AND contype = 'c'
        ORDER BY conname;
        """
    )

    print("\nActive CHECK constraints on exchange_rates:")
    for row in rows:
        name = row["conname"]
        print(f"  [OK] {name}")

    await conn.close()
    print("\nMigration complete.")


asyncio.run(migrate())
