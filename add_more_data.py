#!/usr/bin/env python3

import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.config import settings

async def add_more_floors_and_rooms():
    """Agregar más pisos y habitaciones a la base de datos existente"""

    engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        print("🔧 AGREGANDO MÁS PISOS Y HABITACIONES")
        print("=" * 50)

        # Obtener todas las residencias existentes
        result = await session.execute(
            text("SELECT id, name FROM residence WHERE deleted_at IS NULL")
        )
        residences = result.fetchall()

        print(f"📊 Encontradas {len(residences)} residencias")

        # Estadísticas iniciales
        stats_query = text("""
            SELECT 'floor' as entity, COUNT(*) as total FROM floor WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'room', COUNT(*) FROM room WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'bed', COUNT(*) FROM bed WHERE deleted_at IS NULL
        """)
        result = await session.execute(stats_query)
        initial_stats = {row[0]: row[1] for row in result.fetchall()}

        print(f"📈 Estadísticas iniciales:")
        print(f"   - Pisos: {initial_stats['floor']}")
        print(f"   - Habitaciones: {initial_stats['room']}")
        print(f"   - Camas: {initial_stats['bed']}")

        # Para cada residencia, agregar más pisos si tiene menos de 5
        for residence in residences:
            residence_id, residence_name = residence

            # Obtener pisos existentes para esta residencia
            result = await session.execute(
                text("SELECT id, name FROM floor WHERE residence_id = :residence_id AND deleted_at IS NULL ORDER BY name"),
                {"residence_id": residence_id}
            )
            existing_floors = result.fetchall()

            print(f"\n🏢 Residencia: {residence_name}")
            print(f"   Pisos existentes: {len(existing_floors)}")

            # Si tiene menos de 5 pisos, agregar más
            if len(existing_floors) < 5:
                floors_to_add = 5 - len(existing_floors)
                print(f"   ➕ Agregando {floors_to_add} pisos adicionales...")

                for i in range(floors_to_add):
                    floor_number = len(existing_floors) + i + 1
                    floor_name = f"Piso {floor_number}"

                    # Verificar si ya existe un piso con este nombre
                    result = await session.execute(
                        text("""
                            SELECT id FROM floor
                            WHERE residence_id = :residence_id AND name = :floor_name AND deleted_at IS NULL
                        """),
                        {"residence_id": residence_id, "floor_name": floor_name}
                    )

                    if not result.fetchone():
                        # Insertar nuevo piso
                        floor_id = str(uuid.uuid4())
                        await session.execute(
                            text("""
                                INSERT INTO floor (id, name, residence_id, created_at, updated_at)
                                VALUES (:id, :name, :residence_id, NOW(), NOW())
                            """),
                            {"id": floor_id, "name": floor_name, "residence_id": residence_id}
                        )
                        print(f"      ✅ Creado piso: {floor_name}")

                        # Agregar habitaciones a este nuevo piso (entre 3-6 habitaciones por piso)
                        rooms_per_floor = 3 + (i % 4)  # 3, 4, 5, o 6 habitaciones
                        for room_num in range(1, rooms_per_floor + 1):
                            room_name = f"Habitación {floor_number}{room_num:02d}"
                            room_id = str(uuid.uuid4())

                            await session.execute(
                                text("""
                                    INSERT INTO room (id, name, floor_id, residence_id, created_at, updated_at)
                                    VALUES (:id, :name, :floor_id, :residence_id, NOW(), NOW())
                                """),
                                {"id": room_id, "name": room_name, "floor_id": floor_id, "residence_id": residence_id}
                            )

                            # Agregar 2-4 camas por habitación
                            beds_per_room = 2 + (room_num % 3)  # 2, 3, o 4 camas
                            for bed_num in range(1, beds_per_room + 1):
                                bed_name = f"Cama {floor_number}{room_num:02d}-{bed_num}"
                                bed_id = str(uuid.uuid4())

                                await session.execute(
                                    text("""
                                        INSERT INTO bed (id, name, room_id, residence_id, created_at, updated_at)
                                        VALUES (:id, :name, :room_id, :residence_id, NOW(), NOW())
                                    """),
                                    {"id": bed_id, "name": bed_name, "room_id": room_id, "residence_id": residence_id}
                                )

                        print(f"         🛏️  Agregadas {rooms_per_floor} habitaciones con {beds_per_room} camas cada una")
                    else:
                        print(f"      ⚠️  El piso {floor_name} ya existe")
            else:
                print(f"   ✅ Tiene suficientes pisos ({len(existing_floors)})")

                # Para los pisos existentes, verificar si tienen suficientes habitaciones
                for floor in existing_floors:
                    floor_id, floor_name = floor

                    result = await session.execute(
                        text("SELECT COUNT(*) FROM room WHERE floor_id = :floor_id AND deleted_at IS NULL"),
                        {"floor_id": floor_id}
                    )
                    room_count = result.fetchone()[0]

                    if room_count < 3:
                        # Agregar más habitaciones a este piso
                        rooms_to_add = 3 - room_count
                        print(f"   🏠 Piso {floor_name}: Agregando {rooms_to_add} habitaciones...")

                        for i in range(rooms_to_add):
                            room_number = room_count + i + 1
                            room_name = f"Habitación {floor_name.split()[1]}{room_number:02d}"
                            room_id = str(uuid.uuid4())

                            await session.execute(
                                text("""
                                    INSERT INTO room (id, name, floor_id, residence_id, created_at, updated_at)
                                    VALUES (:id, :name, :floor_id, :residence_id, NOW(), NOW())
                                """),
                                {"id": room_id, "name": room_name, "floor_id": floor_id, "residence_id": residence_id}
                            )

                            # Agregar 2-4 camas por habitación
                            beds_per_room = 2 + (i % 3)
                            for bed_num in range(1, beds_per_room + 1):
                                bed_name = f"Cama {floor_name.split()[1]}{room_number:02d}-{bed_num}"
                                bed_id = str(uuid.uuid4())

                                await session.execute(
                                    text("""
                                        INSERT INTO bed (id, name, room_id, residence_id, created_at, updated_at)
                                        VALUES (:id, :name, :room_id, :residence_id, NOW(), NOW())
                                    """),
                                    {"id": bed_id, "name": bed_name, "room_id": room_id, "residence_id": residence_id}
                                )

                        print(f"        🛏️  Agregadas {rooms_to_add} habitaciones con {beds_per_room} camas cada una")

        # Confirmar cambios
        await session.commit()

        # Mostrar estadísticas finales
        print(f"\n📊 ESTADÍSTICAS FINALES:")
        result = await session.execute(stats_query)
        final_stats = {row[0]: row[1] for row in result.fetchall()}

        print(f"   - Pisos: {final_stats['floor']} (↑ +{final_stats['floor'] - initial_stats['floor']})")
        print(f"   - Habitaciones: {final_stats['room']} (↑ +{final_stats['room'] - initial_stats['room']})")
        print(f"   - Camas: {final_stats['bed']} (↑ +{final_stats['bed'] - initial_stats['bed']})")

        print(f"\n✅ BASE DE DATOS ACTUALIZADA EXITOSAMENTE")

if __name__ == "__main__":
    asyncio.run(add_more_floors_and_rooms())