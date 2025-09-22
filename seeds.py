#!/usr/bin/env python3
# =====================================================================
# SCRIPT DE SEEDS PARA BASE DE DATOS
# =====================================================================
"""
Script unificado para poblar la base de datos con datos de prueba.
Incluye datos realistas y configurables para desarrollo y testing.

Uso:
    python seeds.py                    # Datos básicos para desarrollo
    python seeds.py --full             # Datos completos con grandes volúmenes
    python seeds.py --minimal          # Solo datos mínimos necesarios
"""

import asyncio
import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import List, Dict, Tuple

# Agregar el directorio raíz al path para importar módulos de la app
sys.path.append(str(Path(__file__).parent))

import bcrypt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.config import settings
from app.models import (
    User, Residence, UserResidence, Floor, Room, Bed, Resident, 
    Device, TaskCategory, TaskTemplate, TaskApplication, Measurement, Tag, ResidentTag
)
from app.security import hash_alias

# =====================================================================
# DATOS DE PRUEBA
# =====================================================================

NOMBRES_RESIDENCIAS = [
    "Residencia Santa Clara", "Residencia El Rosal", "Residencia La Esperanza", 
    "Residencia San José", "Residencia Los Olivos", "Residencia La Paz", 
    "Residencia El Roble", "Residencia La Floresta", "Residencia San Juan",
    "Residencia El Mirador", "Residencia La Alameda", "Residencia Las Acacias"
]

NOMBRES_RESIDENTES = [
    "María García López", "Juan Rodríguez Martín", "Ana Martínez Silva", 
    "Carlos López González", "Lucía Fernández Ruiz", "Miguel González Pérez",
    "Carmen Sánchez Torres", "José Ramírez Díaz", "Isabel Torres Moreno",
    "Francisco Díaz Jiménez", "Pilar Jiménez Muñoz", "Antonio Moreno Álvarez",
    "Rosa Muñoz Castro", "Manuel Álvarez Herrera", "Teresa Castro Ortiz",
    "Luis Herrera Ruiz", "Elena Ortiz Vargas", "Javier Ruiz Molina",
    "Marina Vargas Romero", "Ricardo Molina Gómez", "Laura Romero Navarro",
    "David Gómez Martín", "Sofía Navarro Serrano", "Pedro Martín Cruz",
    "Beatriz Serrano Flores", "Alejandro Cruz Gil", "Patricia Flores Vega",
    "Roberto Gil Salas", "Claudia Vega Campos", "Fernando Salas Santos"
]

NOMBRES_USUARIOS = {
    "managers": [
        "Carlos Administrador", "Juan Gestor", "Manuel Director", "Pedro Supervisor",
        "José Coordinador", "Luis Manager", "Miguel Jefe", "Antonio Responsable"
    ],
    "professionals": [
        "María Enfermera", "Ana Doctora", "Carmen Fisioterapeuta", "Isabel Psicóloga",
        "Pilar Nutricionista", "Teresa Trabajadora Social", "Elena Terapeuta",
        "Laura Auxiliar", "Sofía Cuidadora", "Beatriz Especialista"
    ]
}

CATEGORIAS_TAREAS = [
    "Medicación", "Higiene Personal", "Alimentación", "Movilidad", 
    "Control Signos Vitales", "Terapia Física", "Socialización", "Descanso"
]

PLANTILLAS_TAREAS = {
    "Medicación": [
        ("Toma matutina de medicamentos", ["Tomado", "Parcial", "No tomado", "Rechazado"]),
        ("Toma nocturna de medicamentos", ["Tomado", "Parcial", "No tomado", "Rechazado"]),
        ("Control de presión arterial", ["Normal", "Elevada", "Baja", "Crítica"]),
        ("Control de glucosa", ["Normal", "Elevada", "Baja", "Crítica"])
    ],
    "Higiene Personal": [
        ("Aseo matutino", ["Completo", "Parcial", "No realizado", "Rechazado"]),
        ("Cambio de ropa", ["Realizado", "Parcial", "No realizado", "Rechazado"]),
        ("Higiene bucal", ["Completa", "Parcial", "No realizada", "Rechazada"]),
        ("Baño diario", ["Completo", "Parcial", "No realizado", "Rechazado"])
    ],
    "Alimentación": [
        ("Desayuno", ["Completo", "Parcial", "No consumido", "Rechazado"]),
        ("Almuerzo", ["Completo", "Parcial", "No consumido", "Rechazado"]),
        ("Cena", ["Completo", "Parcial", "No consumido", "Rechazado"]),
        ("Colación", ["Completa", "Parcial", "No consumida", "Rechazada"])
    ],
    "Movilidad": [
        ("Transferencia silla-cama", ["Completa", "Con ayuda", "No realizada", "Rechazada"]),
        ("Caminata asistida", ["Realizada", "Con ayuda", "No realizada", "Rechazada"]),
        ("Ejercicios de movilidad", ["Completos", "Parciales", "No realizados", "Rechazados"])
    ]
}

TIPOS_DISPOSITIVOS = ["blood_pressure", "pulse_oximeter", "scale", "thermometer"]

NOMBRES_DISPOSITIVOS = {
    "blood_pressure": ["Tensiómetro Omron HEM-7120", "Tensiómetro Beurer BM28", "Tensiómetro Braun BP6200"],
    "pulse_oximeter": ["Pulsioxímetro Contec CMS50D", "Pulsioxímetro Zacurate Pro", "Pulsioxímetro Wellue O2Ring"],
    "scale": ["Báscula Tanita BC-601", "Báscula Omron BF511", "Báscula Beurer BF700"],
    "thermometer": ["Termómetro Braun ThermoScan 7", "Termómetro iHealth PT3", "Termómetro Withings Thermo"]
}

ETIQUETAS_RESIDENTES = [
    "Diabetes", "Hipertensión", "Movilidad Reducida", "Demencia", "Alzheimer",
    "Cardiovascular", "Respiratorio", "Renal", "Oncológico", "Psiquiátrico",
    "Alergia Medicamentos", "Dieta Especial", "Asistencia Total", "Riesgo Caídas"
]

# =====================================================================
# CLASE PRINCIPAL DE SEEDS
# =====================================================================

class DatabaseSeeder:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.fecha_inicio = datetime.now(timezone.utc) - timedelta(days=365)  # 1 año atrás

    async def hash_password(self, password: str) -> str:
        """Genera hash de contraseña usando bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    async def create_user(self, alias: str, password: str, role: str, name: str = None, email: str = None, phone: str = None, created_by_id: str = None) -> User:
        """Crea un usuario con datos encriptados"""
        user_id = str(uuid.uuid4())
        password_hash = await self.hash_password(password)
        alias_encrypted = hash_alias(alias)
        alias_hash = hash_alias(alias)  # Usar hash_alias en lugar de bcrypt

        user = User(
            id=user_id,
            role=role,
            alias_encrypted=alias.encode('utf-8'),  # Guardar alias original encriptado
            alias_hash=alias_hash,
            password_hash=password_hash,
            name=name,
            created_by=created_by_id,  # NULL para superadmin, ID del creador para otros
            email_encrypted=email.encode('utf-8') if email else None,
            phone_encrypted=phone.encode('utf-8') if phone else None
        )

        self.session.add(user)
        await self.session.flush()
        return user

    async def create_residences(self, count: int) -> List[Residence]:
        """Crea residencias con datos de contacto"""
        print(f"🏠 Creando {count} residencias...")
        residences = []

        for i in range(count):
            residence_id = str(uuid.uuid4())
            name = f"{NOMBRES_RESIDENCIAS[i % len(NOMBRES_RESIDENCIAS)]} {i+1}"
            address = f"Calle Principal {i+1}, Ciudad, País"
            
            # Datos de contacto simulados
            phone = f"+34 91 {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"
            email = f"info@residencia{i+1}.com"

            residence = Residence(
                id=residence_id,
                name=name,
                address=address,
                phone_encrypted=phone.encode('utf-8'),
                email_encrypted=email.encode('utf-8'),
                created_at=self.fecha_inicio + timedelta(days=random.randint(0, 300))
            )

            self.session.add(residence)
            residences.append(residence)

        await self.session.flush()
        return residences

    async def create_structure(self, residences: List[Residence]) -> Tuple[List[Floor], List[Room], List[Bed]]:
        """Crea la estructura de pisos, habitaciones y camas"""
        print("🏗️  Creando estructura de pisos, habitaciones y camas...")
        
        all_floors = []
        all_rooms = []
        all_beds = []

        for residence in residences:
            # Crear 2-4 pisos por residencia
            num_floors = random.randint(2, 4)
            
            for floor_num in range(1, num_floors + 1):
                floor = Floor(
                    id=str(uuid.uuid4()),
                    residence_id=residence.id,
                    name=f"Piso {floor_num}"
                )
                self.session.add(floor)
                all_floors.append(floor)

        # Flush pisos primero
        await self.session.flush()

        for residence in residences:
            # Obtener pisos de esta residencia
            residence_floors = [f for f in all_floors if f.residence_id == residence.id]
            
            for floor in residence_floors:
                # Crear 5-10 habitaciones por piso
                num_rooms = random.randint(5, 10)
                
                for room_num in range(1, num_rooms + 1):
                    room = Room(
                        id=str(uuid.uuid4()),
                        residence_id=residence.id,
                        floor_id=floor.id,
                        name=f"Habitación {floor.name[-1]}{room_num:02d}"
                    )
                    self.session.add(room)
                    all_rooms.append(room)

        # Flush habitaciones
        await self.session.flush()

        for room in all_rooms:
            # Crear 1-3 camas por habitación
            num_beds = random.randint(1, 3)
            
            for bed_num in range(1, num_beds + 1):
                bed = Bed(
                    id=str(uuid.uuid4()),
                    residence_id=room.residence_id,
                    room_id=room.id,
                    name=f"Cama {bed_num}"
                )
                self.session.add(bed)
                all_beds.append(bed)

        # Flush final de camas
        await self.session.flush()
        return all_floors, all_rooms, all_beds

    async def create_residents(self, count: int, beds: List[Bed], residences: List[Residence]) -> List[Resident]:
        """Crea residentes asignados a camas"""
        print(f"👥 Creando {count} residentes...")
        residents = []

        for i in range(count):
            resident_id = str(uuid.uuid4())
            residence = random.choice(residences)
            
            # Filtrar camas de la residencia
            residence_beds = [b for b in beds if b.residence_id == residence.id]
            bed = random.choice(residence_beds) if residence_beds else None

            # Datos del residente
            full_name = NOMBRES_RESIDENTES[i % len(NOMBRES_RESIDENTES)]
            
            # Fecha de nacimiento (65-95 años)
            birth_year = random.randint(1929, 1959)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            birth_date = date(birth_year, birth_month, birth_day)

            resident = Resident(
                id=resident_id,
                residence_id=residence.id,
                full_name=full_name,
                birth_date=birth_date,
                sex=random.choice(["M", "F"]),
                status=random.choice(["active", "active", "active", "discharged"]),  # 75% activos
                bed_id=bed.id if bed else None,
                comments=f"Residente de prueba - {full_name}"
            )

            self.session.add(resident)
            residents.append(resident)

        await self.session.flush()
        return residents

    async def create_task_system(self, residences: List[Residence], creator_id: str = None) -> Tuple[List[TaskCategory], List[TaskTemplate]]:
        """Crea el sistema de categorías y plantillas de tareas"""
        print("📋 Creando sistema de tareas...")
        
        all_categories = []
        all_templates = []

        for residence in residences:
            # Crear categorías para cada residencia
            for category_name in CATEGORIAS_TAREAS:
                category = TaskCategory(
                    id=str(uuid.uuid4()),
                    residence_id=residence.id,
                    name=category_name,
                    created_by=creator_id
                )
                self.session.add(category)
                all_categories.append(category)

                # Crear plantillas para cada categoría
                templates_data = PLANTILLAS_TAREAS.get(category_name, [])
                for template_name, statuses in templates_data:
                    template = TaskTemplate(
                        id=str(uuid.uuid4()),
                        residence_id=residence.id,
                        task_category_id=category.id,
                        name=template_name,
                        status1=statuses[0] if len(statuses) > 0 else None,
                        status2=statuses[1] if len(statuses) > 1 else None,
                        status3=statuses[2] if len(statuses) > 2 else None,
                        status4=statuses[3] if len(statuses) > 3 else None,
                        status5=statuses[4] if len(statuses) > 4 else None,
                        status6=statuses[5] if len(statuses) > 5 else None,
                        created_by=creator_id
                    )
                    self.session.add(template)
                    all_templates.append(template)

        await self.session.flush()
        return all_categories, all_templates

    async def create_devices(self, count: int, residences: List[Residence], users: List[User]) -> List[Device]:
        """Crea dispositivos médicos"""
        print(f"📱 Creando {count} dispositivos...")
        devices = []

        for i in range(count):
            residence = random.choice(residences)
            device_type = random.choice(TIPOS_DISPOSITIVOS)
            device_names = NOMBRES_DISPOSITIVOS[device_type]
            device_name = random.choice(device_names)

            # MAC única
            mac = f"00:1B:44:11:{(i//256):02X}:{(i%256):02X}"

            # Asignar un usuario creador aleatorio
            creator = random.choice(users)

            device = Device(
                id=str(uuid.uuid4()),
                residence_id=residence.id,
                type=device_type,
                name=f"{device_name} #{i+1}",
                mac=mac,
                battery_percent=random.randint(20, 100),
                created_by=creator.id
            )

            self.session.add(device)
            devices.append(device)

        await self.session.flush()
        return devices

    async def create_tags_and_assignments(self, residents: List[Resident], users: List[User]) -> List[Tag]:
        """Crea etiquetas y las asigna a residentes"""
        print("🏷️  Creando etiquetas y asignaciones...")
        tags = []

        # Crear etiquetas
        for tag_name in ETIQUETAS_RESIDENTES:
            tag = Tag(
                id=str(uuid.uuid4()),
                name=tag_name
            )
            self.session.add(tag)
            tags.append(tag)

        await self.session.flush()

        # Asignar etiquetas a residentes aleatoriamente
        for resident in residents:
            # Cada residente tiene 0-3 etiquetas
            num_tags = random.randint(0, 3)
            selected_tags = random.sample(tags, min(num_tags, len(tags)))
            
            for tag in selected_tags:
                assignment = ResidentTag(
                    resident_id=resident.id,
                    tag_id=tag.id,
                    assigned_by=random.choice(users).id,
                    assigned_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 180))
                )
                self.session.add(assignment)

        await self.session.flush()
        return tags

    async def assign_users_to_residences(self, users: List[User], residences: List[Residence]):
        """Asigna usuarios a residencias"""
        print("🔗 Asignando usuarios a residencias...")
        
        for user in users:
            if user.role == "superadmin":
                continue  # Superadmin no necesita asignaciones específicas
                
            # Cada usuario se asigna a 1-3 residencias
            num_residences = random.randint(1, 3)
            assigned_residences = random.sample(residences, min(num_residences, len(residences)))
            
            for residence in assigned_residences:
                assignment = UserResidence(
                    user_id=user.id,
                    residence_id=residence.id
                )
                self.session.add(assignment)

        await self.session.flush()

    async def seed_minimal(self):
        """Seeds mínimos para desarrollo básico"""
        print("🌱 Creando datos mínimos...")
        
        # 1. Superadmin
        superadmin = await self.create_user(
            "admin", "admin123", "superadmin", "Administrador del Sistema",
            "admin@residencias.com", "+34 600 000 000"
        )
        
        # 2. Una residencia
        residences = await self.create_residences(1)
        
        # 3. Un gestor y un profesional
        manager = await self.create_user("manager1", "manager123", "manager", "Gestor Principal", created_by_id=superadmin.id)
        professional = await self.create_user("prof1", "prof123", "professional", "Profesional de Cuidados", created_by_id=superadmin.id)
        
        # 4. Estructura básica
        floors, rooms, beds = await self.create_structure(residences)
        
        # 5. Algunos residentes
        residents = await self.create_residents(10, beds, residences)
        
        # 6. Sistema de tareas básico
        categories, templates = await self.create_task_system(residences, superadmin.id)
        
        # 7. Asignaciones
        await self.assign_users_to_residences([manager, professional], residences)
        
        await self.session.commit()
        print("✅ Datos mínimos creados")

    async def seed_development(self):
        """Seeds para desarrollo completo"""
        print("🌱 Creando datos de desarrollo...")
        
        # 1. Usuarios del sistema
        superadmin = await self.create_user(
            "admin", "admin123", "superadmin", "Administrador del Sistema",
            "admin@residencias.com", "+34 600 000 000"
        )
        
        managers = []
        for i, name in enumerate(NOMBRES_USUARIOS["managers"][:4]):
            manager = await self.create_user(
                f"manager{i+1}", "manager123", "manager", name,
                f"manager{i+1}@residencias.com", f"+34 600 00{i+1} 00{i+1}",
                superadmin.id  # Creado por el superadmin
            )
            managers.append(manager)
        
        professionals = []
        for i, name in enumerate(NOMBRES_USUARIOS["professionals"][:8]):
            prof = await self.create_user(
                f"prof{i+1}", "prof123", "professional", name,
                f"prof{i+1}@residencias.com", f"+34 700 00{i+1} 00{i+1}",
                superadmin.id  # Creado por el superadmin
            )
            professionals.append(prof)
        
        # 2. Residencias
        residences = await self.create_residences(6)
        
        # 3. Estructura
        floors, rooms, beds = await self.create_structure(residences)
        
        # 4. Residentes
        residents = await self.create_residents(60, beds, residences)
        
        # 5. Sistema de tareas
        categories, templates = await self.create_task_system(residences, superadmin.id)
        
        # 6. Usuarios para asignaciones
        all_users = [superadmin] + managers + professionals
        
        # 7. Dispositivos
        devices = await self.create_devices(20, residences, all_users)
        
        # 8. Etiquetas
        tags = await self.create_tags_and_assignments(residents, all_users)
        
        # 8. Asignaciones
        await self.assign_users_to_residences(managers + professionals, residences)
        
        await self.session.commit()
        print("✅ Datos de desarrollo creados")

    async def seed_full(self):
        """Seeds completos con grandes volúmenes"""
        print("🌱 Creando datos completos...")
        
        # 1. Usuarios del sistema
        superadmin = await self.create_user(
            "admin", "admin123", "superadmin", "Administrador del Sistema",
            "admin@residencias.com", "+34 600 000 000"
        )
        
        managers = []
        for i in range(12):
            name = NOMBRES_USUARIOS["managers"][i % len(NOMBRES_USUARIOS["managers"])]
            manager = await self.create_user(
                f"manager{i+1}", "manager123", "manager", name,
                f"manager{i+1}@residencias.com", f"+34 600 {i+100:03d} {i+100:03d}",
                superadmin.id  # Creado por el superadmin
            )
            managers.append(manager)
        
        professionals = []
        for i in range(30):
            name = NOMBRES_USUARIOS["professionals"][i % len(NOMBRES_USUARIOS["professionals"])]
            prof = await self.create_user(
                f"prof{i+1}", "prof123", "professional", name,
                f"prof{i+1}@residencias.com", f"+34 700 {i+100:03d} {i+100:03d}",
                superadmin.id  # Creado por el superadmin
            )
            professionals.append(prof)
        
        # 2. Residencias
        residences = await self.create_residences(12)
        
        # 3. Estructura
        floors, rooms, beds = await self.create_structure(residences)
        
        # 4. Residentes
        residents = await self.create_residents(200, beds, residences)
        
        # 5. Sistema de tareas
        categories, templates = await self.create_task_system(residences, superadmin.id)
        
        # 6. Usuarios para asignaciones
        all_users = [superadmin] + managers + professionals
        
        # 7. Dispositivos
        devices = await self.create_devices(48, residences, all_users)
        
        # 8. Etiquetas
        tags = await self.create_tags_and_assignments(residents, all_users)
        
        # 8. Asignaciones
        await self.assign_users_to_residences(managers + professionals, residences)
        
        await self.session.commit()
        print("✅ Datos completos creados")

    async def print_summary(self):
        """Imprime un resumen de los datos creados"""
        print("\n" + "="*60)
        print("📊 RESUMEN DE DATOS CREADOS")
        print("="*60)
        
        queries = [
            ('Usuarios', 'SELECT COUNT(*) FROM "user"'),
            ('Residencias', 'SELECT COUNT(*) FROM residence'),
            ('Pisos', 'SELECT COUNT(*) FROM floor'),
            ('Habitaciones', 'SELECT COUNT(*) FROM room'),
            ('Camas', 'SELECT COUNT(*) FROM bed'),
            ('Residentes', 'SELECT COUNT(*) FROM resident'),
            ('Categorías de tareas', 'SELECT COUNT(*) FROM task_category'),
            ('Plantillas de tareas', 'SELECT COUNT(*) FROM task_template'),
            ('Dispositivos', 'SELECT COUNT(*) FROM device'),
            ('Etiquetas', 'SELECT COUNT(*) FROM tag'),
        ]
        
        for name, query in queries:
            result = await self.session.execute(text(query))
            count = result.scalar()
            print(f"  {name}: {count}")
        
        print("\n🔑 CREDENCIALES DE ACCESO:")
        print("  - Superadmin: admin / admin123")
        print("  - Gestores: manager1, manager2, ... / manager123")
        print("  - Profesionales: prof1, prof2, ... / prof123")
        print("="*60)

# =====================================================================
# FUNCIÓN PRINCIPAL
# =====================================================================

async def main():
    """Función principal que maneja los argumentos y ejecuta el seeding"""
    parser = argparse.ArgumentParser(description='Script de seeds para la base de datos')
    parser.add_argument('--minimal', action='store_true', help='Solo datos mínimos')
    parser.add_argument('--full', action='store_true', help='Datos completos con grandes volúmenes')
    parser.add_argument('--clear', action='store_true', help='Limpiar datos existentes antes de crear')
    
    args = parser.parse_args()
    
    # Crear engine y sesión
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        seeder = DatabaseSeeder(session)
        
        try:
            if args.clear:
                print("🗑️  Limpiando datos existentes...")
                await session.execute(text("""
                    TRUNCATE measurement, task_application, resident_tag, resident, bed, room, floor, 
                             user_residence, device, task_template, task_category, tag, event_log, 
                             residence, "user" RESTART IDENTITY CASCADE;
                """))
                await session.commit()
                print("✅ Datos limpiados")
            
            if args.minimal:
                await seeder.seed_minimal()
            elif args.full:
                await seeder.seed_full()
            else:
                await seeder.seed_development()
            
            await seeder.print_summary()
            
        except Exception as e:
            print(f"❌ Error durante el seeding: {e}")
            await session.rollback()
            raise
            
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
