#!/usr/bin/env python3
"""
Script to fix duplicate names by adding unique constraints
"""

import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async def fix_unique_names():
    # Database URL
    DATABASE_URL = "postgresql+asyncpg://postgres:159753123.@localhost:5432/residences"

    engine = create_async_engine(DATABASE_URL)

    async with engine.begin() as conn:
        # First, let's check and fix duplicates
        print("Checking for duplicates...")

        # Fix floor names - add suffix to duplicates
        result = await conn.execute(text("""
            WITH duplicates AS (
                SELECT
                    id,
                    name,
                    residence_id,
                    ROW_NUMBER() OVER (PARTITION BY residence_id, name ORDER BY id) as rn
                FROM floor
            )
            UPDATE floor f
            SET name = d.name || ' ' || (d.rn - 1)
            FROM duplicates d
            WHERE d.id = f.id AND d.rn > 1;
        """))
        print(f"Updated {result.rowcount} floor names")

        # Fix room names - add suffix to duplicates
        result = await conn.execute(text("""
            WITH duplicates AS (
                SELECT
                    r.id,
                    r.name,
                    f.residence_id,
                    ROW_NUMBER() OVER (PARTITION BY f.residence_id, r.name ORDER BY r.id) as rn
                FROM room r
                JOIN floor f ON r.floor_id = f.id
            )
            UPDATE room r
            SET name = d.name || ' ' || (d.rn - 1)
            FROM duplicates d
            WHERE d.id = r.id AND d.rn > 1;
        """))
        print(f"Updated {result.rowcount} room names")

        # Fix bed names - add suffix to duplicates
        result = await conn.execute(text("""
            WITH duplicates AS (
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
            SET name = d.name || ' ' || (d.rn - 1)
            FROM duplicates d
            WHERE d.id = b.id AND d.rn > 1;
        """))
        print(f"Updated {result.rowcount} bed names")

        # Add unique constraints
        print("\nAdding unique constraints...")

        # For floor table
        await conn.execute(text("""
            ALTER TABLE floor
            ADD CONSTRAINT uq_floor_residence_name
            UNIQUE (residence_id, name);
        """))
        print("Added unique constraint to floor table")

        # For room table - we'll use a different approach
        # First, add residence_id to room table to make constraint easier
        await conn.execute(text("""
            ALTER TABLE room
            ADD COLUMN residence_id UUID NOT NULL DEFAULT gen_random_uuid(),
            ADD CONSTRAINT fk_room_residence
            FOREIGN KEY (residence_id) REFERENCES residence(id);
        """))

        # Update residence_id based on floor
        await conn.execute(text("""
            UPDATE room r
            SET residence_id = f.residence_id
            FROM floor f
            WHERE f.id = r.floor_id;
        """))

        # Now add unique constraint
        await conn.execute(text("""
            ALTER TABLE room
            ADD CONSTRAINT uq_room_residence_name
            UNIQUE (residence_id, name);
        """))
        print("Added residence_id and unique constraint to room table")

        # For bed table - add residence_id as well
        await conn.execute(text("""
            ALTER TABLE bed
            ADD COLUMN residence_id UUID NOT NULL DEFAULT gen_random_uuid(),
            ADD CONSTRAINT fk_bed_residence
            FOREIGN KEY (residence_id) REFERENCES residence(id);
        """))

        # Update residence_id based on room
        await conn.execute(text("""
            UPDATE bed b
            SET residence_id = r.residence_id
            FROM room r
            WHERE r.id = b.room_id;
        """))

        # Now add unique constraint
        await conn.execute(text("""
            ALTER TABLE bed
            ADD CONSTRAINT uq_bed_residence_name
            UNIQUE (residence_id, name);
        """))
        print("Added residence_id and unique constraint to bed table")

        # For residence table (name should be globally unique)
        await conn.execute(text("""
            ALTER TABLE residence
            ADD CONSTRAINT uq_residence_name
            UNIQUE (name);
        """))
        print("Added unique constraint to residence table")

        # For task_category table (unique by residence)
        await conn.execute(text("""
            ALTER TABLE task_category
            ADD CONSTRAINT uq_task_category_residence_name
            UNIQUE (residence_id, name);
        """))
        print("Added unique constraint to task_category table")

        # For task_template table (unique by category)
        await conn.execute(text("""
            ALTER TABLE task_template
            ADD CONSTRAINT uq_task_template_category_name
            UNIQUE (category_id, name);
        """))
        print("Added unique constraint to task_template table")

        # For device table (unique by residence)
        await conn.execute(text("""
            ALTER TABLE device
            ADD CONSTRAINT uq_device_residence_name
            UNIQUE (residence_id, name);
        """))
        print("Added unique constraint to device table")

        # For tag table (unique by residence)
        await conn.execute(text("""
            ALTER TABLE tag
            ADD CONSTRAINT uq_tag_residence_name
            UNIQUE (residence_id, name);
        """))
        print("Added unique constraint to tag table")

    print("\nUnique constraints added successfully!")

    # Verify no duplicates remain
    async with AsyncSession(engine) as session:
        result = await session.execute(text("""
            SELECT COUNT(*) as remaining_duplicates
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
            ) as duplicates;
        """))

        remaining = result.scalar_one()
        if remaining == 0:
            print("✓ No duplicates remaining!")
        else:
            print(f"✗ {remaining} duplicates still remain!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_unique_names())