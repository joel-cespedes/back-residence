#!/usr/bin/env python3
"""
Script para crear los enums en la base de datos
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def main():
    """Crear todos los enums en la base de datos"""
    engine = create_async_engine(settings.database_url, echo=True)

    async with engine.begin() as conn:
        # Crear enums
        enums = [
            "CREATE TYPE user_role_enum AS ENUM ('superadmin', 'manager', 'professional')",
            "CREATE TYPE resident_status_enum AS ENUM ('active', 'discharged', 'deceased')",
            "CREATE TYPE device_type_enum AS ENUM ('blood_pressure', 'pulse_oximeter', 'scale', 'thermometer')",
            "CREATE TYPE measurement_type_enum AS ENUM ('bp', 'spo2', 'weight', 'temperature')",
            "CREATE TYPE measurement_source_enum AS ENUM ('device', 'voice', 'manual')",
        ]

        for enum_sql in enums:
            try:
                await conn.execute(text(enum_sql))
                print(f"✅ Creado: {enum_sql}")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"⚠️  Ya existe: {enum_sql}")
                else:
                    print(f"❌ Error: {enum_sql} - {e}")

    await engine.dispose()
    print("✅ Enums creados exitosamente")

if __name__ == "__main__":
    asyncio.run(main())