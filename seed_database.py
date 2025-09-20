#!/usr/bin/env python3
"""
Script to seed the database with test data
"""

import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import uuid
import random
from datetime import date

# Names for test data
RESIDENCE_NAMES = [
    "Residencia San Miguel", "Residencia San Antonio", "Residencia Santa María",
    "Residencia San José", "Residencia San Francisco", "Residencia San Juan",
    "Residencia San Pedro", "Residencia San Pablo", "Residencia San Mateo",
    "Residencia San Lucas"
]

FIRST_NAMES = [
    "María", "José", "Carmen", "Juan", "Ana", "Francisco", "Isabel", "Antonio",
    "Dolores", "Manuel", "Teresa", "Jesús", "Lucía", "David", "Elena", "Miguel",
    "Rosa", "Javier", "Patricia", "Carlos", "Sofía", "Alejandro", "Marta",
    "Fernando", "Laura", "Pedro", "Cristina", "Pablo", "Beatriz", "Roberto"
]

LAST_NAMES = [
    "García", "Rodríguez", "González", "Fernández", "López", "Martínez",
    "Sánchez", "Pérez", "Gómez", "Martín", "Jiménez", "Ruiz",
    "Hernández", "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero",
    "Alonso", "Gutiérrez", "Navarro", "Torres", "Domínguez", "Vargas"
]

async def seed_database():
    DATABASE_URL = "postgresql+asyncpg://postgres:159753123.@localhost:5432/residences"
    engine = create_async_engine(DATABASE_URL)

    async with engine.begin() as conn:
        print("Cleaning existing data...")
        # Use CASCADE to delete all data including user table
        await conn.execute(text("TRUNCATE measurement, task_application, resident_tag, resident, bed, room, floor, residence CASCADE;"))
        await conn.execute(text("TRUNCATE \"user\" CASCADE;"))

        print("Creating residences...")
        residences = []
        for i, name in enumerate(RESIDENCE_NAMES):
            residence_id = str(uuid.uuid4())
            residences.append({
                'id': residence_id,
                'name': name,
                'address': f'Dirección {name} #{i+1}'
            })
            await conn.execute(text(
                "INSERT INTO residence (id, name, address, created_at, updated_at) "
                "VALUES (:id, :name, :address, NOW(), NOW())"
            ), residences[-1])

        print("Creating floors...")
        floors = []
        for residence in residences:
            num_floors = random.randint(3, 6)
            for floor_num in range(1, num_floors + 1):
                floor_id = str(uuid.uuid4())
                floor_name = f'Piso {floor_num}'
                floors.append({
                    'id': floor_id,
                    'name': floor_name,
                    'residence_id': residence['id']
                })
                await conn.execute(text(
                    "INSERT INTO floor (id, name, residence_id, created_at, updated_at) "
                    "VALUES (:id, :name, :residence_id, NOW(), NOW())"
                ), floors[-1])

        print("Creating rooms and beds...")
        beds = []
        for floor in floors:
            num_rooms = random.randint(8, 15)
            for room_num in range(1, num_rooms + 1):
                room_id = str(uuid.uuid4())
                room_name = f'Habitación {room_num:03d}'

                # Create room
                await conn.execute(text(
                    "INSERT INTO room (id, name, floor_id, residence_id, created_at, updated_at) "
                    "VALUES (:id, :name, :floor_id, :residence_id, NOW(), NOW())"
                ), {
                    'id': room_id,
                    'name': room_name,
                    'floor_id': floor['id'],
                    'residence_id': floor['residence_id']
                })

                # Create beds for this room (usually 1-4 beds per room)
                num_beds = random.randint(1, 4)
                for bed_num in range(1, num_beds + 1):
                    bed_id = str(uuid.uuid4())
                    bed_name = f'Cama {bed_num}'
                    beds.append({
                        'id': bed_id,
                        'name': bed_name,
                        'room_id': room_id,
                        'floor_id': floor['id'],
                        'residence_id': floor['residence_id']
                    })
                    await conn.execute(text(
                        "INSERT INTO bed (id, name, room_id, residence_id, created_at, updated_at) "
                        "VALUES (:id, :name, :room_id, :residence_id, NOW(), NOW())"
                    ), beds[-1])

        print(f"Created {len(beds)} beds")

        print("Creating residents...")
        residents = []
        for i in range(300):
            if i % 50 == 0:
                print(f"Creating resident {i+1}/300...")

            # Select a random bed
            bed = random.choice(beds)

            resident_id = str(uuid.uuid4())
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            full_name = f"{first_name} {last_name}"

            # Generate random birth date (between 50 and 90 years old)
            birth_year = random.randint(1934, 1974)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            birth_date = date(birth_year, birth_month, birth_day)

            sex = random.choice(['M', 'F'])
            gender = random.choice(['Masculino', 'Femenino', 'Otro', 'Prefiero no decir'])

            residents.append({
                'id': resident_id,
                'full_name': full_name,
                'birth_date': birth_date,
                'sex': sex,
                'gender': gender,
                'residence_id': bed['residence_id'],
                'bed_id': bed['id'],
                'status': random.choice(['active', 'discharged', 'deceased']),
                'comments': f'Residente creado automáticamente - {full_name}'
            })

            await conn.execute(text(
                "INSERT INTO resident (id, full_name, birth_date, sex, gender, residence_id, bed_id, status, comments, created_at, updated_at) "
                "VALUES (:id, :full_name, :birth_date, :sex, :gender, :residence_id, :bed_id, :status, :comments, NOW(), NOW())"
            ), residents[-1])

        print("Creating admin and test users...")
        # Create admin user first
        await conn.execute(text("""
            INSERT INTO "user" (id, alias_encrypted, alias_hash, password_hash, role, created_at, updated_at)
            VALUES ('00000000-0000-0000-0000-000000000000', '\\x', 'admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6', 'superadmin', NOW(), NOW())
        """))

        test_users = [
            {'alias': 'user1', 'role': 'superadmin'},
            {'alias': 'user2', 'role': 'manager'},
            {'alias': 'user3', 'role': 'manager'},
        ]

        for user_data in test_users:
            user_id = str(uuid.uuid4())
            await conn.execute(text(
                "INSERT INTO \"user\" (id, alias_encrypted, alias_hash, password_hash, role, created_at, updated_at) "
                "VALUES (:id, '\\x', :alias, 'fake_hash_for_now', :role, NOW(), NOW())"
            ), {'id': user_id, **user_data})

        print("\nDatabase seeded successfully!")
        print(f"\nSummary:")
        print(f"- {len(residences)} residences")
        print(f"- {len(floors)} floors")
        print(f"- {len(RESIDENCE_NAMES) * 45} rooms (approximately)")
        print(f"- {len(beds)} beds")
        print(f"- {len(residents)} residents")
        print(f"- {len(test_users) + 1} test users (including admin)")

        print("\nYou can now test with:")
        print("- Username: admin, Password: admin123")
        print("- Username: user1, Password: admin123")
        print("- Username: user2, Password: admin123")
        print("- Username: user3, Password: admin123")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_database())
