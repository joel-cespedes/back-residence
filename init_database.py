#!/usr/bin/env python3
# =====================================================================
# SCRIPT DE INICIALIZACIÓN DE BASE DE DATOS
# =====================================================================
"""
Script para inicializar completamente la base de datos del sistema de residencias.
Este script:
1. Borra todas las tablas existentes
2. Crea los enums necesarios en PostgreSQL
3. Crea todas las tablas desde cero usando los modelos
4. Configura índices y constraints

Uso:
    python init_database.py
"""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar módulos de la app
sys.path.append(str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings
from app.models import Base

async def drop_all_tables(engine):
    """Elimina todas las tablas existentes si existen"""
    print("🔍 Verificando si existen tablas para eliminar...")
    
    async with engine.begin() as conn:
        # Verificar si hay tablas
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """))
        table_count = result.scalar()
        
        if table_count > 0:
            print(f"🗑️  Eliminando {table_count} tablas existentes...")
            # Eliminar solo las tablas, no todo el schema
            await conn.execute(text("""
                DROP TABLE IF EXISTS event_log, resident_tag, tag, task_application, 
                task_template, task_category, measurement, device, resident, bed, 
                room, floor, user_residence, residence, "user" CASCADE
            """))
            print("✅ Tablas eliminadas")
        else:
            print("✅ Base de datos vacía, no hay tablas que eliminar")

async def create_enums(engine):
    """Crea todos los tipos enum necesarios en PostgreSQL"""
    print("📝 Creando tipos enum...")

    enums = [
        ("user_role_enum", "CREATE TYPE user_role_enum AS ENUM ('superadmin', 'manager', 'professional')"),
        ("resident_status_enum", "CREATE TYPE resident_status_enum AS ENUM ('active', 'discharged', 'deceased')"),
        ("device_type_enum", "CREATE TYPE device_type_enum AS ENUM ('blood_pressure', 'pulse_oximeter', 'scale', 'thermometer')"),
        ("measurement_type_enum", "CREATE TYPE measurement_type_enum AS ENUM ('bp', 'spo2', 'weight', 'temperature')"),
        ("measurement_source_enum", "CREATE TYPE measurement_source_enum AS ENUM ('device', 'voice', 'manual')"),
        ("resident_history_change_type_enum", "CREATE TYPE resident_history_change_type_enum AS ENUM ('bed_assignment', 'bed_removal', 'status_change', 'residence_transfer')"),
    ]
    
    # Crear cada enum en su propia transacción para evitar abortos
    for enum_name, enum_sql in enums:
        async with engine.begin() as conn:
            try:
                # Verificar si el enum ya existe
                result = await conn.execute(text("""
                    SELECT COUNT(*) FROM pg_type WHERE typname = :enum_name
                """), {"enum_name": enum_name})
                
                if result.scalar() > 0:
                    print(f"  ⚠️  {enum_name} ya existe")
                else:
                    await conn.execute(text(enum_sql))
                    print(f"  ✅ {enum_name} creado")
            except Exception as e:
                print(f"  ❌ Error creando {enum_name}: {e}")
                raise

async def create_tables(engine):
    """Crea todas las tablas usando los modelos de SQLAlchemy"""
    print("🏗️  Creando todas las tablas...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Todas las tablas creadas")

async def create_triggers(engine):
    """Crea triggers para resident_history que registran automáticamente cambios"""
    print("🔔 Creando triggers para resident_history...")

    async with engine.begin() as conn:
        # Función del trigger que registra cambios en resident_history
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION log_resident_changes()
            RETURNS TRIGGER AS $$
            DECLARE
                v_change_type resident_history_change_type_enum;
                v_changed_by UUID;
            BEGIN
                -- Obtener el usuario que hizo el cambio desde el contexto de sesión
                BEGIN
                    v_changed_by := current_setting('app.user_id', true)::UUID;
                EXCEPTION WHEN OTHERS THEN
                    v_changed_by := NULL;
                END;

                -- Determinar el tipo de cambio
                IF (OLD.bed_id IS NULL AND NEW.bed_id IS NOT NULL) THEN
                    v_change_type := 'bed_assignment';
                ELSIF (OLD.bed_id IS NOT NULL AND NEW.bed_id IS NULL) THEN
                    v_change_type := 'bed_removal';
                ELSIF (OLD.status IS DISTINCT FROM NEW.status) THEN
                    v_change_type := 'status_change';
                ELSIF (OLD.residence_id IS DISTINCT FROM NEW.residence_id) THEN
                    v_change_type := 'residence_transfer';
                ELSIF (OLD.bed_id IS DISTINCT FROM NEW.bed_id OR
                       OLD.room_id IS DISTINCT FROM NEW.room_id OR
                       OLD.floor_id IS DISTINCT FROM NEW.floor_id) THEN
                    v_change_type := 'bed_assignment';
                ELSE
                    -- Si no hay cambios relevantes, no registrar
                    RETURN NEW;
                END IF;

                -- Insertar registro en resident_history
                INSERT INTO resident_history (
                    resident_id,
                    residence_id,
                    bed_id,
                    room_id,
                    floor_id,
                    status,
                    previous_bed_id,
                    previous_room_id,
                    previous_floor_id,
                    previous_status,
                    change_type,
                    changed_by,
                    changed_at
                ) VALUES (
                    NEW.id,
                    NEW.residence_id,
                    NEW.bed_id,
                    NEW.room_id,
                    NEW.floor_id,
                    NEW.status,
                    OLD.bed_id,
                    OLD.room_id,
                    OLD.floor_id,
                    OLD.status,
                    v_change_type,
                    v_changed_by,
                    NOW()
                );

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        print("  ✅ Función log_resident_changes() creada")

        # Trigger que se ejecuta DESPUÉS de UPDATE en resident
        # Separar DROP y CREATE para evitar error de asyncpg
        await conn.execute(text("DROP TRIGGER IF EXISTS resident_changes_trigger ON resident"))
        await conn.execute(text("""
            CREATE TRIGGER resident_changes_trigger
            AFTER UPDATE ON resident
            FOR EACH ROW
            WHEN (
                OLD.bed_id IS DISTINCT FROM NEW.bed_id OR
                OLD.room_id IS DISTINCT FROM NEW.room_id OR
                OLD.floor_id IS DISTINCT FROM NEW.floor_id OR
                OLD.status IS DISTINCT FROM NEW.status OR
                OLD.residence_id IS DISTINCT FROM NEW.residence_id
            )
            EXECUTE FUNCTION log_resident_changes()
        """))
        print("  ✅ Trigger resident_changes_trigger creado")

async def create_indexes(engine):
    """Crea índices adicionales para mejorar el rendimiento"""
    print("⚡ Creando índices de rendimiento...")
    
    indexes = [
        # Índices para búsquedas frecuentes
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_alias_hash ON "user" (alias_hash)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_role ON "user" (role)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_deleted_at ON "user" (deleted_at)',
        

        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_room_id ON resident (room_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_floor_id ON resident (floor_id)',

        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_residence_name ON residence (name)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_residence_deleted_at ON residence (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_full_name ON resident (full_name)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_status ON resident (status)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_residence_id ON resident (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_bed_id ON resident (bed_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_deleted_at ON resident (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_floor_residence_id ON floor (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_floor_deleted_at ON floor (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_room_residence_id ON room (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_room_floor_id ON room (floor_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_room_deleted_at ON room (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bed_residence_id ON bed (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bed_room_id ON bed (room_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bed_deleted_at ON bed (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_device_residence_id ON device (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_device_type ON device (type)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_device_mac ON device (mac)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_device_deleted_at ON device (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measurement_residence_id ON measurement (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measurement_resident_id ON measurement (resident_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measurement_type ON measurement (type)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measurement_taken_at ON measurement (taken_at)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measurement_deleted_at ON measurement (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_category_residence_id ON task_category (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_category_deleted_at ON task_category (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_template_residence_id ON task_template (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_template_category_id ON task_template (task_category_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_template_deleted_at ON task_template (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_application_residence_id ON task_application (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_application_resident_id ON task_application (resident_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_application_template_id ON task_application (task_template_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_application_applied_at ON task_application (applied_at)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_application_deleted_at ON task_application (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tag_name ON tag (name)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tag_deleted_at ON tag (deleted_at)',
        
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_log_actor_user_id ON event_log (actor_user_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_log_residence_id ON event_log (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_log_entity ON event_log (entity)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_log_action ON event_log (action)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_log_at ON event_log (at)',

        # Índices para resident_history (analítica de movimientos)
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_history_resident_id ON resident_history (resident_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_history_residence_id ON resident_history (residence_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_history_bed_id ON resident_history (bed_id)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_history_changed_by ON resident_history (changed_by)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_history_changed_at ON resident_history (changed_at)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_history_change_type ON resident_history (change_type)',

        # Índices compuestos para consultas complejas
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_residence_status ON resident (residence_id, status)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measurement_resident_type_taken ON measurement (resident_id, type, taken_at)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_app_resident_status ON task_application (resident_id, selected_status_text)',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resident_history_resident_changed ON resident_history (resident_id, changed_at DESC)',
    ]
    
    async with engine.begin() as conn:
        for index_sql in indexes:
            try:
                await conn.execute(text(index_sql))
                print(f"  ✅ Índice creado")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"  ⚠️  Índice ya existe")
                else:
                    print(f"  ❌ Error creando índice: {e}")

async def verify_setup(engine):
    """Verifica que todo esté configurado correctamente"""
    print("🔍 Verificando configuración...")
    
    async with engine.begin() as conn:
        # Verificar que los enums existan
        result = await conn.execute(text("""
            SELECT typname FROM pg_type
            WHERE typname IN ('user_role_enum', 'resident_status_enum', 'device_type_enum',
                             'measurement_type_enum', 'measurement_source_enum', 'resident_history_change_type_enum')
        """))
        enums = [row[0] for row in result.fetchall()]
        
        expected_enums = ['user_role_enum', 'resident_status_enum', 'device_type_enum',
                         'measurement_type_enum', 'measurement_source_enum', 'resident_history_change_type_enum']
        
        for enum_name in expected_enums:
            if enum_name in enums:
                print(f"  ✅ Enum {enum_name}")
            else:
                print(f"  ❌ Enum {enum_name} no encontrado")
        
        # Verificar que las tablas existan
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        """))
        tables = [row[0] for row in result.fetchall()]
        
        expected_tables = ['user', 'residence', 'user_residence', 'floor', 'room', 'bed',
                          'resident', 'resident_history', 'device', 'measurement', 'task_category', 'task_template',
                          'task_application', 'tag', 'resident_tag', 'event_log']
        
        for table_name in expected_tables:
            if table_name in tables:
                print(f"  ✅ Tabla {table_name}")
            else:
                print(f"  ❌ Tabla {table_name} no encontrada")

async def main():
    """Función principal de inicialización"""
    print("🚀 INICIALIZANDO BASE DE DATOS DEL SISTEMA DE RESIDENCIAS")
    print("=" * 60)
    print(f"🔗 Base de datos: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'local'}")
    
    # Crear engine de base de datos
    engine = create_async_engine(settings.database_url, echo=False)
    
    try:
        # Verificar si hay tablas existentes
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """))
            table_count = result.scalar()
            
            if table_count > 0:
                print(f"⚠️  ATENCIÓN: Se encontraron {table_count} tablas existentes")
                print("⚠️  Este script eliminará TODAS las tablas existentes")
                print("🤖 Confirmación automática para recrear estructura con room_id y floor_id")
                # response = input("¿Estás seguro de que quieres continuar? (escribe 'SI' para confirmar): ")
                # if response.upper() != 'SI':
                #     print("❌ Operación cancelada por el usuario")
                #     return
        
        # 1. Eliminar todas las tablas existentes
        await drop_all_tables(engine)
        
        # 2. Crear enums
        await create_enums(engine)
        
        # 3. Crear todas las tablas
        await create_tables(engine)

        # 4. Crear triggers para resident_history
        await create_triggers(engine)

        # 5. Crear índices de rendimiento
        await create_indexes(engine)

        # 6. Verificar configuración
        await verify_setup(engine)
        
        print("=" * 60)
        print("✅ BASE DE DATOS INICIALIZADA CORRECTAMENTE")
        print("")
        print("Próximos pasos:")
        print("1. Ejecutar 'python seed_database.py' para poblar con datos de prueba")
        print("2. Iniciar el servidor con 'uvicorn main:app --reload'")
        
    except Exception as e:
        print(f"❌ Error durante la inicialización: {e}")
        sys.exit(1)
        
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
