#!/usr/bin/env python3

import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config import settings

async def check_bed():
    # Crear engine
    engine = create_async_engine(settings.database_url)

    # Crear sesión
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        # Verificar si la cama existe
        bed_id = '79c2d201-a5b3-4fb0-8ad0-905ac2c1c71c'

        print(f"Buscando cama con ID: {bed_id}")

        # Buscar la cama específica
        result = await session.execute(
            text('SELECT * FROM bed WHERE id = :id'),
            {'id': bed_id}
        )
        bed = result.fetchone()

        if bed:
            print("✅ Cama encontrada:")
            print(dict(bed))
        else:
            print("❌ Cama no encontrada")

            # Verificar si hay camas en la base de datos
            result = await session.execute(text('SELECT COUNT(*) FROM bed'))
            count = result.fetchone()[0]
            print(f"Total de camas en la base de datos: {count}")

            if count > 0:
                # Mostrar todas las camas
                result = await session.execute(text('SELECT id, name, room_id FROM bed'))
                print("\n📋 Todas las camas en la base de datos:")
                for row in result:
                    print(f"  ID: {row[0]}, Name: {row[1]}, Room ID: {row[2]}")

            # Verificar si la tabla existe
            try:
                result = await session.execute(text('SELECT * FROM bed LIMIT 1'))
                print("✅ Tabla 'bed' existe y es accesible")
            except Exception as e:
                print(f"❌ Error al acceder a la tabla 'bed': {e}")

if __name__ == "__main__":
    asyncio.run(check_bed())