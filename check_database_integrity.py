#!/usr/bin/env python3

import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select
from app.config import settings
from app.models import Residence, Floor, Room, Bed, Resident

async def check_database_integrity():
    """Verificar la integridad referencial completa de la base de datos"""

    engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        print("🔍 ANALIZANDO INTEGRIDAD REFERENCIAL DE LA BASE DE DATOS")
        print("=" * 60)

        # 1. Verificar camas sin habitación válida
        print("\n1. 🔍 VERIFICANDO CAMAS SIN HABITACIÓN VÁLIDA:")
        query = text("""
            SELECT b.id, b.name, b.room_id, r.id as room_exists
            FROM bed b
            LEFT JOIN room r ON b.room_id = r.id
            WHERE r.id IS NULL AND b.deleted_at IS NULL
        """)
        result = await session.execute(query)
        invalid_beds = result.fetchall()

        if invalid_beds:
            print(f"❌ SE ENCONTRARON {len(invalid_beds)} CAMAS CON HABITACIÓN INVÁLIDA:")
            for bed in invalid_beds:
                print(f"   - Cama ID: {bed[0]}, Nombre: {bed[1]}, Room ID inválido: {bed[2]}")
        else:
            print("✅ Todas las camas tienen habitaciones válidas")

        # 2. Verificar habitaciones sin piso válido
        print("\n2. 🔍 VERIFICANDO HABITACIONES SIN PISO VÁLIDO:")
        query = text("""
            SELECT r.id, r.name, r.floor_id, f.id as floor_exists
            FROM room r
            LEFT JOIN floor f ON r.floor_id = f.id
            WHERE f.id IS NULL AND r.deleted_at IS NULL
        """)
        result = await session.execute(query)
        invalid_rooms = result.fetchall()

        if invalid_rooms:
            print(f"❌ SE ENCONTRARON {len(invalid_rooms)} HABITACIONES CON PISO INVÁLIDO:")
            for room in invalid_rooms:
                print(f"   - Habitación ID: {room[0]}, Nombre: {room[1]}, Floor ID inválido: {room[2]}")
        else:
            print("✅ Todas las habitaciones tienen pisos válidos")

        # 3. Verificar pisos sin residencia válida
        print("\n3. 🔍 VERIFICANDO PISOS SIN RESIDENCIA VÁLIDA:")
        query = text("""
            SELECT f.id, f.name, f.residence_id, r.id as residence_exists
            FROM floor f
            LEFT JOIN residence r ON f.residence_id = r.id
            WHERE r.id IS NULL AND f.deleted_at IS NULL
        """)
        result = await session.execute(query)
        invalid_floors = result.fetchall()

        if invalid_floors:
            print(f"❌ SE ENCONTRARON {len(invalid_floors)} PISOS CON RESIDENCIA INVÁLIDA:")
            for floor in invalid_floors:
                print(f"   - Piso ID: {floor[0]}, Nombre: {floor[1]}, Residence ID inválido: {floor[2]}")
        else:
            print("✅ Todos los pisos tienen residencias válidas")

        # 4. Verificar residentes sin cama válida
        print("\n4. 🔍 VERIFICANDO RESIDENTES SIN CAMA VÁLIDA:")
        query = text("""
            SELECT res.id, res.full_name, res.bed_id, b.id as bed_exists
            FROM resident res
            LEFT JOIN bed b ON res.bed_id = b.id
            WHERE b.id IS NULL AND res.deleted_at IS NULL
        """)
        result = await session.execute(query)
        invalid_residents = result.fetchall()

        if invalid_residents:
            print(f"❌ SE ENCONTRARON {len(invalid_residents)} RESIDENTES CON CAMA INVÁLIDA:")
            for resident in invalid_residents:
                print(f"   - Residente ID: {resident[0]}, Nombre: {resident[1]}, Bed ID inválido: {resident[2]}")
        else:
            print("✅ Todos los residentes tienen camas válidas")

        # 5. Verificar IDs duplicados o inconsistentes
        print("\n5. 🔍 VERIFICANDO IDS DUPLICADOS O INCONSISTENTES:")

        # Verificar si hay IDs que aparecen en múltiples tablas (conflicto de tipos)
        query = text("""
            SELECT 'bed' as table_name, id FROM bed WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'room' as table_name, id FROM room WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'floor' as table_name, id FROM floor WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'residence' as table_name, id FROM residence WHERE deleted_at IS NULL
        """)
        result = await session.execute(query)
        all_ids = result.fetchall()

        # Agrupar por ID para encontrar duplicados
        id_counts = {}
        for row in all_ids:
            id_val = row[1]
            if id_val not in id_counts:
                id_counts[id_val] = []
            id_counts[id_val].append(row[0])

        duplicate_ids = {id_val: tables for id_val, tables in id_counts.items() if len(tables) > 1}

        if duplicate_ids:
            print(f"❌ SE ENCONTRARON {len(duplicate_ids)} IDS QUE APARECEN EN MÚLTIPLES TABLAS:")
            for id_val, tables in duplicate_ids.items():
                print(f"   - ID {id_val} aparece en: {', '.join(tables)}")
        else:
            print("✅ No hay IDs duplicados entre diferentes tipos de entidades")

        # 6. Verificar el caso específico del ID problemático
        print("\n6. 🔍 INVESTIGANDO EL ID PROBLEMÁTICO ESPECÍFICO:")
        problematic_id = '79c2d201-a5b3-4fb0-8ad0-905ac2c1c71c'

        # Buscar en todas las tablas
        tables_to_check = [
            ('residence', 'id'),
            ('floor', 'id'),
            ('room', 'id'),
            ('bed', 'id'),
            ('resident', 'id')
        ]

        found_in = []
        for table_name, id_column in tables_to_check:
            query = text(f"SELECT id FROM {table_name} WHERE id = :id AND deleted_at IS NULL")
            result = await session.execute(query, {'id': problematic_id})
            if result.fetchone():
                found_in.append(table_name)

        if found_in:
            print(f"❌ EL ID {problematic_id} APARECE EN: {', '.join(found_in)}")
        else:
            print(f"✅ El ID {problematic_id} no existe en ninguna tabla")

        # 7. Conteo total de registros
        print("\n7. 📊 CONTEO TOTAL DE REGISTROS:")
        counts_query = text("""
            SELECT
                'residence' as table_name, COUNT(*) as total FROM residence WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'floor', COUNT(*) FROM floor WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'room', COUNT(*) FROM room WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'bed', COUNT(*) FROM bed WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'resident', COUNT(*) FROM resident WHERE deleted_at IS NULL
        """)
        result = await session.execute(counts_query)
        counts = result.fetchall()

        for table_name, total in counts:
            print(f"   - {table_name.title()}: {total}")

        print("\n" + "=" * 60)
        print("🔍 ANÁLISIS COMPLETADO")

        # Resumen de problemas encontrados
        total_problems = (
            len(invalid_beds) +
            len(invalid_rooms) +
            len(invalid_floors) +
            len(invalid_residents) +
            len(duplicate_ids)
        )

        if total_problems > 0:
            print(f"\n❌ SE ENCONTRARON {total_problems} PROBLEMAS DE INTEGRIDAD REFERENCIAL")
            print("   ¡LA BASE DE DATOS TIENE INCONSISTENCIAS QUE DEBEN CORREGIRSE!")
        else:
            print("\n✅ INTEGRIDAD REFERENCIAL CORRECTA")
            print("   La base de datos mantiene todas las relaciones correctamente")

if __name__ == "__main__":
    asyncio.run(check_database_integrity())