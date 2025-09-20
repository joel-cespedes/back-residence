#!/usr/bin/env python3

import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select
from app.config import settings

async def investigate_specific_id():
    """Investigar el conflicto específico del ID"""

    engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        print("🔍 INVESTIGANDO CONFLICTO DE ID ESPECÍFICO")
        print("=" * 60)

        problematic_id = '79c2d201-a5b3-4fb0-8ad0-905ac2c1c71c'

        # Buscar información detallada de la room con este ID
        print(f"\n1. 📋 INFORMACIÓN DE LA ROOM CON ID {problematic_id}:")

        query = text("""
            SELECT r.id, r.name, r.floor_id, f.name as floor_name,
                   f.residence_id, res.name as residence_name
            FROM room r
            LEFT JOIN floor f ON r.floor_id = f.id
            LEFT JOIN residence res ON f.residence_id = res.id
            WHERE r.id = :id AND r.deleted_at IS NULL
        """)
        result = await session.execute(query, {'id': problematic_id})
        room_info = result.fetchone()

        if room_info:
            print(f"✅ ROOM ENCONTRADA:")
            print(f"   - ID: {room_info[0]}")
            print(f"   - Nombre: {room_info[1]}")
            print(f"   - Floor ID: {room_info[2]}")
            print(f"   - Floor Nombre: {room_info[3]}")
            print(f"   - Residence ID: {room_info[4]}")
            print(f"   - Residence Nombre: {room_info[5]}")
        else:
            print("❌ ROOM NO ENCONTRADA")

        # Verificar si hay camas asociadas a esta room
        print(f"\n2. 🛏️ CAMAS ASOCIADAS A ESTA ROOM:")

        query = text("""
            SELECT id, name, room_id
            FROM bed
            WHERE room_id = :room_id AND deleted_at IS NULL
            ORDER BY name
        """)
        result = await session.execute(query, {'room_id': problematic_id})
        beds = result.fetchall()

        if beds:
            print(f"✅ SE ENCONTRARON {len(beds)} CAMAS EN ESTA ROOM:")
            for bed in beds:
                print(f"   - Bed ID: {bed[0]}, Nombre: {bed[1]}")
        else:
            print("❌ NO HAY CAMAS EN ESTA ROOM")

        # Verificar si hay residentes asociados a estas camas
        print(f"\n3. 👥 RESIDENTES EN LAS CAMAS DE ESTA ROOM:")

        if beds:
            bed_ids = [bed[0] for bed in beds]
            placeholders = ','.join([f':id{i}' for i in range(len(bed_ids))])
            params = {f'id{i}': bed_id for i, bed_id in enumerate(bed_ids)}

            query = text(f"""
                SELECT id, full_name, bed_id, status
                FROM resident
                WHERE bed_id IN ({placeholders}) AND deleted_at IS NULL
                ORDER BY full_name
            """)
            result = await session.execute(query, params)
            residents = result.fetchall()

            if residents:
                print(f"✅ SE ENCONTRARON {len(residents)} RESIDENTES:")
                for resident in residents:
                    print(f"   - Residente: {resident[1]}, Bed ID: {resident[2]}, Status: {resident[3]}")
            else:
                print("❌ NO HAY RESIDENTES EN ESTAS CAMAS")

        # Verificar el endpoint que causó el error
        print(f"\n4. 🔍 ANÁLISIS DEL ENDPOINT PROBLEMÁTICO:")
        print(f"   - URL llamada: /structure/beds/{problematic_id}/simple")
        print(f"   - ID proporcionado: {problematic_id}")
        print(f"   - Tipo real de ID: ROOM")
        print(f"   - Endpoint esperaba: BED ID")
        print(f"   - ⚠️  CONFLICTO: Se llamó a endpoint de bed con ID de room")

        # Investigar si hay un problema de rutas en FastAPI
        print(f"\n5. 🛣️  ANÁLISIS DE POSIBLE CONFLICTO DE RUTAS:")
        print(f"   - Ruta individual bed: /beds/{{id}}")
        print(f"   - Ruta simple bed: /beds/{{id}}/simple")
        print(f"   - Ruta room beds: /beds/{{room_id}}/simple")
        print(f"   - ⚠️  POSIBLE PROBLEMA: FastAPI podría estar resolviendo mal las rutas")

        # Verificar estadísticas completas
        print(f"\n6. 📊 ESTADÍSTICAS COMPLETAS:")

        stats_query = text("""
            SELECT
                'residence' as entity, COUNT(*) as total
            FROM residence WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'floor', COUNT(*) FROM floor WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'room', COUNT(*) FROM room WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'bed', COUNT(*) FROM bed WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'resident', COUNT(*) FROM resident WHERE deleted_at IS NULL
            UNION ALL
            SELECT 'resident_without_bed', COUNT(*)
            FROM resident WHERE bed_id IS NULL AND deleted_at IS NULL
        """)
        result = await session.execute(stats_query)
        stats = result.fetchall()

        for stat in stats:
            print(f"   - {stat[0]}: {stat[1]}")

        print(f"\n" + "=" * 60)
        print("🔍 INVESTIGACIÓN COMPLETADA")

if __name__ == "__main__":
    asyncio.run(investigate_specific_id())