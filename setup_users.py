#!/usr/bin/env python3
"""
Script para configurar usuarios con roles y permisos correctos
"""

import asyncio
import sys
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.security import hash_alias

async def setup_users():
    DATABASE_URL = "postgresql+asyncpg://postgres:159753123.@localhost:5432/residences"
    engine = create_async_engine(DATABASE_URL)

    async with engine.begin() as conn:
        print("Configurando usuarios y roles...")

        # Obtener todas las residencias
        result = await conn.execute(text("SELECT id, name FROM residence ORDER BY name"))
        residences = result.fetchall()

        print(f"Residencias disponibles: {len(residences)}")

        # Actualizar usuarios con contraseñas reales
        users_config = [
            {
                'alias': 'admin',
                'password': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6',  # admin123
                'role': 'superadmin',
                'description': 'Superadministrador - Acceso total al sistema'
            },
            {
                'alias': 'manager.sanmiguel',
                'password': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6',  # admin123
                'role': 'manager',
                'description': 'Manager de Residencia San Miguel'
            },
            {
                'alias': 'manager.sanantonio',
                'password': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6',  # admin123
                'role': 'manager',
                'description': 'Manager de Residencia San Antonio'
            },
            {
                'alias': 'manager.santamaria',
                'password': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6',  # admin123
                'role': 'manager',
                'description': 'Manager de Residencia Santa María'
            },
            {
                'alias': 'profesional1',
                'password': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6',  # admin123
                'role': 'professional',
                'description': 'Profesional médico'
            },
            {
                'alias': 'profesional2',
                'password': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6',  # admin123
                'role': 'professional',
                'description': 'Profesional de enfermería'
            }
        ]

        # Limpiar todos los usuarios y residencias
        await conn.execute(text("DELETE FROM user_residence"))
        await conn.execute(text("DELETE FROM \"user\""))

        # Crear usuarios
        created_users = []
        for user_config in users_config:
            alias_hash = hash_alias(user_config['alias'])
            user_id = str(uuid.uuid4())

            await conn.execute(text("""
                INSERT INTO "user" (id, alias_encrypted, alias_hash, password_hash, role, created_at, updated_at)
                VALUES (:id, '\\x', :alias_hash, :password_hash, :role, NOW(), NOW())
            """), {
                'id': user_id,
                'alias_hash': alias_hash,
                'password_hash': user_config['password'],
                'role': user_config['role']
            })

            created_users.append({
                'id': user_id,
                'alias': user_config['alias'],
                'role': user_config['role'],
                'description': user_config['description']
            })

        print(f"\nUsuarios creados:")
        for user in created_users:
            print(f"  - {user['alias']}: {user['role']} - {user['description']}")

        # Asignar residencias a los managers
        print(f"\nAsignando residencias a managers...")

        # Asignar residencias específicas a cada manager
        manager_assignments = [
            ('manager.sanmiguel', 'Residencia San Miguel'),
            ('manager.sanantonio', 'Residencia San Antonio'),
            ('manager.santamaria', 'Residencia Santa María'),
        ]

        for manager_alias, residence_name in manager_assignments:
            # Buscar IDs
            user_result = await conn.execute(
                text("SELECT id FROM \"user\" WHERE alias_hash = :alias_hash"),
                {'alias_hash': hash_alias(manager_alias)}
            )
            user_id = user_result.scalar_one()

            residence_result = await conn.execute(
                text("SELECT id FROM residence WHERE name = :name"),
                {'name': residence_name}
            )
            residence_id = residence_result.scalar_one()

            # Crear asignación
            await conn.execute(text("""
                INSERT INTO user_residence (user_id, residence_id, created_at, updated_at)
                VALUES (:user_id, :residence_id, NOW(), NOW())
            """), {
                'user_id': user_id,
                'residence_id': residence_id
            })

            print(f"  - {manager_alias} asignado a {residence_name}")

        # Asignar todas las residencias a los profesionales (acceso general)
        professional_assignments = [
            ('profesional1', None),  # Acceso a todas
            ('profesional2', None),  # Acceso a todas
        ]

        for professional_alias, specific_residence in professional_assignments:
            user_result = await conn.execute(
                text("SELECT id FROM \"user\" WHERE alias_hash = :alias_hash"),
                {'alias_hash': hash_alias(professional_alias)}
            )
            user_id = user_result.scalar_one()

            if specific_residence:
                # Asignar a una residencia específica
                residence_result = await conn.execute(
                    text("SELECT id FROM residence WHERE name = :name"),
                    {'name': specific_residence}
                )
                residence_id = residence_result.scalar_one()

                await conn.execute(text("""
                    INSERT INTO user_residence (user_id, residence_id, created_at, updated_at)
                    VALUES (:user_id, :residence_id, NOW(), NOW())
                """), {
                    'user_id': user_id,
                    'residence_id': residence_id
                })
                print(f"  - {professional_alias} asignado a {specific_residence}")
            else:
                # Asignar a todas las residencias
                for residence in residences:
                    await conn.execute(text("""
                        INSERT INTO user_residence (user_id, residence_id, created_at, updated_at)
                        VALUES (:user_id, :residence_id, NOW(), NOW())
                    """), {
                        'user_id': user_id,
                        'residence_id': residence.id
                    })
                print(f"  - {professional_alias} asignado a todas las residencias")

        print(f"\nCredenciales para testing:")
        print(f"================================")
        print(f"🔑 SUPERADMIN:")
        print(f"   Alias: admin")
        print(f"   Password: admin123")
        print(f"   Permisos: Acceso total a todo el sistema")
        print(f"")
        print(f"👨‍💼 MANAGERS:")
        print(f"   Alias: manager.sanmiguel")
        print(f"   Password: admin123")
        print(f"   Permisos: Gestiona Residencia San Miguel")
        print(f"")
        print(f"   Alias: manager.sanantonio")
        print(f"   Password: admin123")
        print(f"   Permisos: Gestiona Residencia San Antonio")
        print(f"")
        print(f"   Alias: manager.santamaria")
        print(f"   Password: admin123")
        print(f"   Permisos: Gestiona Residencia Santa María")
        print(f"")
        print(f"👩‍⚕️ PROFESIONALES:")
        print(f"   Alias: profesional1")
        print(f"   Password: admin123")
        print(f"   Permisos: Acceso a todas las residencias (limitado)")
        print(f"")
        print(f"   Alias: profesional2")
        print(f"   Password: admin123")
        print(f"   Permisos: Acceso a todas las residencias (limitado)")
        print(f"")

        # Mostrar resumen final
        result = await conn.execute(text("""
            SELECT u.role, COUNT(ur.residence_id) as residence_count
            FROM "user" u
            LEFT JOIN user_residence ur ON u.id = ur.user_id
            GROUP BY u.role, u.id
            ORDER BY u.role
        """))
        user_summary = result.fetchall()

        print(f"\nResumen de asignaciones:")
        for role, count in user_summary:
            print(f"  {role}: {count} residencia(s) asignada(s)")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(setup_users())