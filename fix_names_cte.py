#!/usr/bin/env python3
"""
Script to fix duplicate names using CTEs
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
        await conn.execute(text("""
            WITH numbered_floors AS (
                SELECT
                    id,
                    name,
                    residence_id,
                    ROW_NUMBER() OVER (PARTITION BY residence_id, name ORDER BY id) as rn
                FROM floor
            )
            UPDATE floor f
            SET name = nf.name || ' ' || (nf.rn - 1)
            FROM numbered_floors nf
            WHERE nf.id = f.id AND nf.rn > 1;
        """))
        print("Fixed duplicate floor names")

        print("\nFixing duplicate room names...")
        await conn.execute(text("""
            WITH numbered_rooms AS (
                SELECT
                    r.id,
                    r.name,
                    f.residence_id,
                    ROW_NUMBER() OVER (PARTITION BY f.residence_id, r.name ORDER BY r.id) as rn
                FROM room r
                JOIN floor f ON r.floor_id = f.id
            )
            UPDATE room r
            SET name = nr.name || ' ' || (nr.rn - 1)
            FROM numbered_rooms nr
            WHERE nr.id = r.id AND nr.rn > 1;
        """))
        print("Fixed duplicate room names")

        print("\nFixing duplicate bed names...")
        await conn.execute(text("""
            WITH numbered_beds AS (
                SELECT
                    b.id,
                    b.name,
                    f.residence_id,
                    ROW_NUMBER() OVER (PARTITION BY f.residence_id, b.name ORDER BY b.id) as rn
                FROM bed b
                JOIN room r ON b.room_id = r.id
                JOIN floor f ON r.floor_id = f.id
            )
            UPDATE bed b
            SET name = nb.name || ' ' || (nb.rn - 1)
            FROM numbered_beds nb
            WHERE nb.id = b.id AND nb.rn > 1;
        """))
        print("Fixed duplicate bed names")

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

        print("\nChecking for problematic floor...")
        result = await conn.execute(text("""
            SELECT id, name, residence_id
            FROM floor
            WHERE id = '893b1a9b-ff91-4b52-b641-f4182ceed3e0'
            OR id = '4df773ab-9c1f-4c23-8797-2a5084a20e4c'
            ORDER BY name;
        """))
        for row in result:
            print(f"ID: {row[0]}, Name: {row[1]}, Residence: {row[2]}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_duplicate_names())