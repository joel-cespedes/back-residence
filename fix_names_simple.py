#!/usr/bin/env python3
"""
Simple script to fix duplicate names
"""

import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def fix_duplicate_names():
    DATABASE_URL = "postgresql+asyncpg://postgres:159753123.@localhost:5432/residences"
    engine = create_async_engine(DATABASE_URL)

    async with engine.begin() as conn:
        print("Fixing duplicate floor names...")
        result = await conn.execute(text("""
            UPDATE floor f
            SET name = f.name || ' ' || (ROW_NUMBER() OVER (PARTITION BY f.residence_id, f.name ORDER BY f.id) - 1)
            FROM (
                SELECT id, residence_id, name,
                       ROW_NUMBER() OVER (PARTITION BY residence_id, name ORDER BY id) as rn
                FROM floor
            ) dups
            WHERE dups.id = f.id AND dups.rn > 1;
        """))
        print(f"Updated {result.rowcount} duplicate floor names")

        print("\nFixing duplicate room names...")
        result = await conn.execute(text("""
            UPDATE room r
            SET name = r.name || ' ' || (ROW_NUMBER() OVER (PARTITION BY f.residence_id, r.name ORDER BY r.id) - 1)
            FROM (
                SELECT r.id, f.residence_id, r.name,
                       ROW_NUMBER() OVER (PARTITION BY f.residence_id, r.name ORDER BY r.id) as rn
                FROM room r
                JOIN floor f ON r.floor_id = f.id
            ) dups
            WHERE dups.id = r.id AND dups.rn > 1;
        """))
        print(f"Updated {result.rowcount} duplicate room names")

        print("\nFixing duplicate bed names...")
        result = await conn.execute(text("""
            UPDATE bed b
            SET name = b.name || ' ' || (ROW_NUMBER() OVER (PARTITION BY f.residence_id, b.name ORDER BY b.id) - 1)
            FROM (
                SELECT b.id, f.residence_id, b.name,
                       ROW_NUMBER() OVER (PARTITION BY f.residence_id, b.name ORDER BY b.id) as rn
                FROM bed b
                JOIN room r ON b.room_id = r.id
                JOIN floor f ON r.floor_id = f.id
            ) dups
            WHERE dups.id = b.id AND dups.rn > 1;
        """))
        print(f"Updated {result.rowcount} duplicate bed names")

        print("\nVerifying fixes...")
        result = await conn.execute(text("""
            SELECT COUNT(*) as remaining
            FROM (
                SELECT residence_id, name, COUNT(*) as count
                FROM floor
                GROUP BY residence_id, name
                HAVING COUNT(*) > 1
                UNION ALL
                SELECT f.residence_id, r.name, COUNT(*) as count
                FROM room r
                JOIN floor f ON r.floor_id = f.id
                GROUP BY f.residence_id, r.name
                HAVING COUNT(*) > 1
                UNION ALL
                SELECT f.residence_id, b.name, COUNT(*) as count
                FROM bed b
                JOIN room r ON b.room_id = r.id
                JOIN floor f ON r.floor_id = f.id
                GROUP BY f.residence_id, b.name
                HAVING COUNT(*) > 1
            ) duplicates;
        """))
        remaining = result.scalar_one()
        if remaining == 0:
            print("✓ All duplicates fixed!")
        else:
            print(f"✗ {remaining} duplicates still remain!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_duplicate_names())