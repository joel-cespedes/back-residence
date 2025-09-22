#!/usr/bin/env python3
# =====================================================================
# SCRIPT SEGURO PARA CREAR SOLO LAS TABLAS
# =====================================================================
"""
Script seguro que SOLO crea las tablas sin eliminar nada existente.
Perfecto para bases de datos nuevas o cuando no quieres tocar datos existentes.

Uso:
    python create_tables_only.py
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

async def create_enums_safe(engine):
    """Crea todos los tipos enum necesarios en PostgreSQL (solo si no existen)"""
    print("📝 Creando tipos enum (solo si no existen)...")
    
    enums = [
        ("user_role_enum", "CREATE TYPE user_role_enum AS ENUM ('superadmin', 'manager', 'professional')"),
        ("resident_status_enum", "CREATE TYPE resident_status_enum AS ENUM ('active', 'discharged', 'deceased')"),
        ("device_type_enum", "CREATE TYPE device_type_enum AS ENUM ('blood_pressure', 'pulse_oximeter', 'scale', 'thermometer')"),
        ("measurement_type_enum", "CREATE TYPE measurement_type_enum AS ENUM ('bp', 'spo2', 'weight', 'temperature')"),
        ("measurement_source_enum", "CREATE TYPE measurement_source_enum AS ENUM ('device', 'voice', 'manual')"),
    ]
    
    # Crear cada enum en su propia transacción
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

async def create_tables_safe(engine):
    """Crea todas las tablas usando los modelos de SQLAlchemy (solo si no existen)"""
    print("🏗️  Creando tablas (solo si no existen)...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Tablas creadas o verificadas")

async def verify_setup(engine):
    """Verifica que todo esté configurado correctamente"""
    print("🔍 Verificando configuración...")
    
    async with engine.begin() as conn:
        # Verificar que los enums existan
        result = await conn.execute(text("""
            SELECT typname FROM pg_type 
            WHERE typname IN ('user_role_enum', 'resident_status_enum', 'device_type_enum', 
                             'measurement_type_enum', 'measurement_source_enum')
        """))
        enums = [row[0] for row in result.fetchall()]
        
        expected_enums = ['user_role_enum', 'resident_status_enum', 'device_type_enum', 
                         'measurement_type_enum', 'measurement_source_enum']
        
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
                          'resident', 'device', 'measurement', 'task_category', 'task_template', 
                          'task_application', 'tag', 'resident_tag', 'event_log']
        
        for table_name in expected_tables:
            if table_name in tables:
                print(f"  ✅ Tabla {table_name}")
            else:
                print(f"  ❌ Tabla {table_name} no encontrada")

async def main():
    """Función principal de creación segura"""
    print("🚀 CREANDO TABLAS DEL SISTEMA DE RESIDENCIAS (MODO SEGURO)")
    print("=" * 60)
    print(f"🔗 Base de datos: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'local'}")
    print("ℹ️  Este script NO elimina nada existente, solo crea lo que falta")
    
    # Crear engine de base de datos
    engine = create_async_engine(settings.database_url, echo=False)
    
    try:
        # 1. Crear enums de forma segura
        await create_enums_safe(engine)
        
        # 2. Crear todas las tablas de forma segura
        await create_tables_safe(engine)
        
        # 3. Verificar configuración
        await verify_setup(engine)
        
        print("=" * 60)
        print("✅ TABLAS CREADAS CORRECTAMENTE")
        print("")
        print("Próximos pasos:")
        print("1. Ejecutar 'python seeds.py' para poblar con datos de prueba")
        print("2. Iniciar el servidor con 'uvicorn main:app --reload'")
        
    except Exception as e:
        print(f"❌ Error durante la creación: {e}")
        sys.exit(1)
        
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
