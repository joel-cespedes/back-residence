#!/usr/bin/env python3
"""
Script para poblar la base de datos con datos realistas de prueba
para el sistema de gestión de residencias - VOLUMEN GRANDE
"""

import asyncio
import random
from datetime import datetime, timedelta, date, timezone
from typing import List
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from app.models import Base, User, Residence, UserResidence, Floor, Room, Bed, Resident, Device, TaskCategory, TaskTemplate, TaskApplication, Measurement
from app.security import hash_alias
import bcrypt
from app.config import settings

# Configuración de la base de datos
engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Datos de ejemplo
NOMBRES_RESIDENTES = [
    "María García", "Juan Rodríguez", "Ana Martínez", "Carlos López", "Lucía Fernández",
    "Miguel González", "Carmen Sánchez", "José Ramírez", "Isabel Torres", "Francisco Díaz",
    "Pilar Jiménez", "Antonio Moreno", "Rosa Muñoz", "Manuel Álvarez", "Teresa Castro",
    "Luis Herrera", "Elena Ortiz", "Javier Ruiz", "Marina Vargas", "Ricardo Molina",
    "Laura Romero", "David Gómez", "Sofía Navarro", "Pedro Martín", "Beatriz Serrano",
    "Alejandro Cruz", "Patricia Flores", "Roberto Gil", "Claudia Vega", "Fernando Salas",
    "Mónica Campos", "Sergio Santos", "Daniela Medina", "Adrián Luna", "Valeria Ríos",
    "Carlos Mendoza", "Gabriela Castro", "Eduardo Peña", "Natalia Herrera", "Óscar Vargas"
]

NOMBRES_RESIDENCIAS = [
    "Residencia Santa Clara", "Residencia El Rosal", "Residencia La Esperanza", "Residencia San José",
    "Residencia Los Olivos", "Residencia La Paz", "Residencia El Roble", "Residencia La Floresta",
    "Residencia San Juan", "Residencia El Mirador", "Residencia La Alameda", "Residencia Las Acacias",
    "Residencia El Prado", "Residencia La Colina", "Residencia San Francisco", "Residencia El Bosque",
    "Residencia La Roca", "Residencia El Lago", "Residencia San Antonio", "Residencia La Montana",
    "Residencia El Jardín", "Residencia La Cima", "Residencia San Pedro", "Residencia El Valle",
    "Residencia La Fuente", "Residencia El Sol", "Residencia San Miguel", "Residencia La Luna"
]

APELLIDOS_COMUNES = ["García", "Rodríguez", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Fernández", "González", "Díaz"]

NOMBRES_GESTORES = ["Carlos", "Juan", "Manuel", "Pedro", "José", "Luis", "Miguel", "Antonio", "Francisco", "Javier", "David", "Alejandro", "Sergio", "Jorge", "Roberto"]

NOMBRES_PROFESIONALES = ["María", "Ana", "Carmen", "Isabel", "Pilar", "Teresa", "Elena", "Laura", "Sofía", "Beatriz", "Patricia", "Mónica", "Gabriela", "Natalia", "Valeria", "Daniela", "Claudia", "Rosa", "Lucía", "Marta"]

TIPOS_DISPOSITIVOS = ["blood_pressure", "pulse_oximeter", "scale", "thermometer"]

NOMBRES_DISPOSITIVOS = {
    "blood_pressure": ["Tensiómetro Omron", "Tensiómetro Beurer", "Tensiómetro Braun", "Tensiómetro Philips"],
    "pulse_oximeter": ["Pulsioxímetro Contec", "Pulsioxímetro Zacurate", "Pulsioxímetro Wellue", "Pulsioxímetro SantaMedical"],
    "scale": ["Báscula Tanita", "Báscula Omron", "Báscula Beurer", "Báscula Withings"],
    "thermometer": ["Termómetro Braun", "Termómetro iHealth", "Termómetro Withings", "Termómetro Beurer"]
}

CATEGORIAS_TAREAS = [
    "Medicación", "Higiene Personal", "Alimentación", "Movilidad", "Control Signos Vitales",
    "Terapia Física", "Socialización", "Descanso", "Ejercicio", "Entretenimiento",
    "Aseo Personal", "Cuidado Piel", "Podología", "Optometría", "Audiometría",
    "Terapia Ocupacional", "Psicología", "Nutrición", "Enfermería"
]

PLANTILLAS_TAREAS = {
    "Medicación": [
        ("Toma matutina de medicamentos", "Tomado", "Parcial", "No tomado", "Rechazado", "Con efectos", "Sin efectos"),
        ("Toma nocturna de medicamentos", "Tomado", "Parcial", "No tomado", "Rechazado", "Con efectos", "Sin efectos"),
        ("Control de presión arterial", "Normal", "Elevada", "Baja", "Crítica", "Controlada", "No controlada"),
        ("Inyección intramuscular", "Aplicada", "Parcial", "No aplicada", "Rechazada", "Con efectos", "Sin efectos"),
        ("Control de glucosa", "Normal", "Elevada", "Baja", "Crítica", "Controlada", "No controlada")
    ],
    "Higiene Personal": [
        ("Aseo matutino", "Completo", "Parcial", "No realizado", "Rechazado", "Con ayuda", "Independiente"),
        ("Cambio de ropa", "Realizado", "Parcial", "No realizado", "Rechazado", "Con ayuda", "Independiente"),
        ("Higiene bucal", "Completa", "Parcial", "No realizada", "Rechazada", "Con ayuda", "Independiente"),
        ("Baño diario", "Completo", "Parcial", "No realizado", "Rechazado", "Con ayuda", "Independiente"),
        ("Corte de uñas", "Realizado", "Parcial", "No realizado", "Rechazado", "Con ayuda", "Independiente")
    ],
    "Alimentación": [
        ("Desayuno", "Completo", "Parcial", "No consumido", "Rechazado", "Con ayuda", "Independiente"),
        ("Almuerzo", "Completo", "Parcial", "No consumido", "Rechazado", "Con ayuda", "Independiente"),
        ("Cena", "Completo", "Parcial", "No consumido", "Rechazado", "Con ayuda", "Independiente"),
        ("Colación matutina", "Completa", "Parcial", "No consumida", "Rechazada", "Con ayuda", "Independiente"),
        ("Colación vespertina", "Completa", "Parcial", "No consumida", "Rechazada", "Con ayuda", "Independiente")
    ],
    "Movilidad": [
        ("Transferencia silla-cama", "Completa", "Parcial", "No realizada", "Rechazada", "Con ayuda", "Independiente"),
        ("Caminata asistida", "Realizada", "Parcial", "No realizada", "Rechazada", "Con ayuda", "Independiente"),
        ("Ejercicios de movilidad", "Completos", "Parciales", "No realizados", "Rechazados", "Con ayuda", "Independiente"),
        ("Uso de andador", "Correcto", "Parcial", "No utilizado", "Rechazado", "Con ayuda", "Independiente"),
        ("Terapia de marcha", "Completada", "Parcial", "No realizada", "Rechazada", "Con ayuda", "Independiente")
    ]
}

class EnhancedDataSeeder:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.fecha_inicio = datetime.now(timezone.utc) - timedelta(days=730)  # 2 años atrás

    async def hash_password(self, password: str) -> str:
        """Hash de contraseña usando bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    async def create_user(self, alias: str, password: str, role: str, full_name: str = None) -> User:
        """Crea un usuario con contraseña hasheada"""
        user_id = str(uuid.uuid4())
        password_hash = await self.hash_password(password)
        alias_encrypted = hash_alias(alias)
        alias_hash = bcrypt.hashpw(alias.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        user = User(
            id=user_id,
            role=role,
            alias_encrypted=alias_encrypted.encode('utf-8'),
            alias_hash=alias_hash,
            password_hash=password_hash
        )

        self.session.add(user)
        await self.session.flush()
        return user

    async def seed_residences(self, count: int = 28) -> List[Residence]:
        """Crea residencias"""
        print(f"🏠 Creando {count} residencias...")
        residences = []

        for i in range(count):
            residence_id = str(uuid.uuid4())
            residence_name = NOMBRES_RESIDENCIAS[i % len(NOMBRES_RESIDENCIAS)]

            residence = Residence(
                id=residence_id,
                name=f"{residence_name} {i+1}",
                address=f"Calle Principal {i+1}, Ciudad, País"
            )

            self.session.add(residence)
            residences.append(residence)

        await self.session.flush()
        return residences

    async def seed_managers(self, count: int = 36) -> List[User]:
        """Crea gestores"""
        print(f"👔 Creando {count} gestores...")
        managers = []

        for i in range(count):
            nombre = NOMBRES_GESTORES[i % len(NOMBRES_GESTORES)]
            apellido = random.choice(APELLIDOS_COMUNES)
            full_name = f"{nombre} {apellido}"

            manager = await self.create_user(
                alias=f"gestor{i+1}",
                password="manager123",
                role="manager",
                full_name=full_name
            )
            managers.append(manager)

        return managers

    async def seed_professionals(self, count: int = 80) -> List[User]:
        """Crea profesionales"""
        print(f"👩‍⚕️ Creando {count} profesionales...")
        professionals = []

        for i in range(count):
            nombre = NOMBRES_PROFESIONALES[i % len(NOMBRES_PROFESIONALES)]
            apellido = random.choice(APELLIDOS_COMUNES)
            full_name = f"{nombre} {apellido}"

            professional = await self.create_user(
                alias=f"profesional{i+1}",
                password="prof123",
                role="professional",
                full_name=full_name
            )
            professionals.append(professional)

        return professionals

    async def assign_managers_to_residences(self, managers: List[User], residences: List[Residence]):
        """Asigna gestores a residencias aleatoriamente"""
        print("🔗 Asignando gestores a residencias...")

        for manager in managers:
            # Cada gestor asignado a 1-3 residencias
            num_residences = random.randint(1, 3)
            assigned_residences = random.sample(residences, min(num_residences, len(residences)))

            for residence in assigned_residences:
                assignment = UserResidence(
                    user_id=manager.id,
                    residence_id=residence.id
                )
                self.session.add(assignment)

    async def create_floors_for_residences(self, residences: List[Residence]) -> dict:
        """Crea pisos para las residencias y devuelve un diccionario de residence_id -> floors"""
        print("🏗️ Creando pisos para residencias...")
        floors_by_residence = {}

        for residence in residences:
            # Crear 2-5 pisos por residencia
            num_floors = random.randint(2, 5)
            floors = []

            for floor_num in range(1, num_floors + 1):
                floor = Floor(
                    id=str(uuid.uuid4()),
                    residence_id=residence.id,
                    name=f"Piso {floor_num}"
                )
                floors.append(floor)
                self.session.add(floor)

            floors_by_residence[residence.id] = floors

        await self.session.flush()
        return floors_by_residence

    async def seed_rooms(self, count: int = 80, residences: List[Residence] = None, floors_by_residence: dict = None) -> List[Room]:
        """Crea habitaciones asignadas a residencias"""
        print(f"🚪 Creando {count} habitaciones...")
        rooms = []

        if not residences or not floors_by_residence:
            return rooms

        for i in range(count):
            residence = random.choice(residences)
            floors = floors_by_residence.get(residence.id, [])

            if not floors:
                continue

            floor = random.choice(floors)
            room_id = str(uuid.uuid4())

            room = Room(
                id=room_id,
                residence_id=residence.id,
                floor_id=floor.id,
                name=f"Habitación {i+1:03d}"
            )

            self.session.add(room)
            rooms.append(room)

        await self.session.flush()
        return rooms

    async def seed_beds(self, rooms: List[Room] = None) -> List[Bed]:
        """Crea camas para habitaciones"""
        print("🛏️ Creando camas para habitaciones...")
        beds = []

        if not rooms:
            return beds

        for i, room in enumerate(rooms):
            # Cada habitación tiene 1-4 camas
            num_beds = random.randint(1, 4)

            for j in range(num_beds):
                bed_id = str(uuid.uuid4())

                bed = Bed(
                    id=bed_id,
                    residence_id=room.residence_id,
                    room_id=room.id,
                    name=f"Cama {j+1}"
                )

                self.session.add(bed)
                beds.append(bed)

        await self.session.flush()
        return beds

    async def seed_residents(self, count: int = 160, beds: List[Bed] = None, residences: List[Residence] = None) -> List[Resident]:
        """Crea residentes asignados a camas"""
        print(f"👴 Creando {count} residentes...")
        residents = []

        if not beds or not residences:
            return residents

        for i in range(count):
            resident_id = str(uuid.uuid4())
            residence = random.choice(residences)

            # Asignar cama aleatoriamente
            bed = random.choice(beds)

            # Fecha de nacimiento aleatoria (60-95 años)
            birth_year = random.randint(1929, 1964)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            birth_date = date(birth_year, birth_month, birth_day)

            resident = Resident(
                id=resident_id,
                residence_id=residence.id,
                full_name=NOMBRES_RESIDENTES[i % len(NOMBRES_RESIDENTES)],
                birth_date=birth_date,
                sex=random.choice(["Masculino", "Femenino"]),
                status=random.choice(["active", "active", "active", "discharged"]), # 75% activos
                bed_id=bed.id
            )

            self.session.add(resident)
            residents.append(resident)

        await self.session.flush()
        return residents

    async def seed_task_categories(self, residences: List[Residence] = None) -> List[TaskCategory]:
        """Crea categorías de tareas para cada residencia"""
        print("📋 Creando categorías de tareas...")
        categories = []

        if not residences:
            return categories

        for residence in residences:
            # Cada residencia tiene 18 categorías
            for i, category_name in enumerate(CATEGORIAS_TAREAS[:18]):
                category_id = str(uuid.uuid4())

                category = TaskCategory(
                    id=category_id,
                    residence_id=residence.id,
                    name=category_name
                )

                self.session.add(category)
                categories.append(category)

        await self.session.flush()
        return categories

    async def seed_task_templates(self, categories: List[TaskCategory] = None) -> List[TaskTemplate]:
        """Crea plantillas de tareas para cada categoría"""
        print("📝 Creando plantillas de tareas...")
        templates = []

        if not categories:
            return templates

        for category in categories:
            # Crear 20 plantillas por categoría (usando las disponibles y repitiendo)
            available_templates = PLANTILLAS_TAREAS.get(category.name, [])

            for i in range(20):
                if available_templates:
                    template_data = random.choice(available_templates)
                else:
                    template_data = ("Tarea genérica", "Completada", "Parcial", "No completada", "Rechazada", "Bien", "Mal")

                template_id = str(uuid.uuid4())

                template = TaskTemplate(
                    id=template_id,
                    residence_id=category.residence_id,
                    task_category_id=category.id,
                    name=template_data[0],
                    status1=template_data[1],
                    status2=template_data[2],
                    status3=template_data[3],
                    status4=template_data[4],
                    status5=template_data[5],
                    status6=template_data[6]
                )

                self.session.add(template)
                templates.append(template)

        await self.session.flush()
        return templates

    async def seed_task_applications(self, residents: List[Resident] = None, templates: List[TaskTemplate] = None, users: List[User] = None) -> List[TaskApplication]:
        """Crea aplicaciones de tareas para residentes"""
        print("📋 Creando aplicaciones de tareas...")
        applications = []

        if not residents or not templates or not users:
            return applications

        # Crear aplicaciones para cada residente
        for resident in residents:
            # Cada residente tiene 5-15 tareas asignadas
            num_tasks = random.randint(5, 15)

            # Filtrar plantillas de la misma residencia
            resident_templates = [t for t in templates if t.residence_id == resident.residence_id]

            if not resident_templates:
                continue

            assigned_templates = random.sample(resident_templates, min(num_tasks, len(resident_templates)))

            for template in assigned_templates:
                # Seleccionar un usuario real (gestor o profesional)
                applied_by = random.choice(users).id

                application = TaskApplication(
                    id=str(uuid.uuid4()),
                    residence_id=resident.residence_id,
                    resident_id=resident.id,
                    task_template_id=template.id,
                    applied_by=applied_by,
                    selected_status_index=random.choice([None, 0, 1, 2, 3]),
                    selected_status_text=random.choice([None, template.status1, template.status2, template.status3])
                )

                self.session.add(application)
                applications.append(application)

        await self.session.flush()
        return applications

    async def seed_devices(self, count: int = 40, residences: List[Residence] = None) -> List[Device]:
        """Crea dispositivos distribuidos en residencias"""
        print(f"📱 Creando {count} dispositivos...")
        devices = []

        if not residences:
            return devices

        for i in range(count):
            residence = random.choice(residences)
            device_type = random.choice(TIPOS_DISPOSITIVOS)
            device_names = NOMBRES_DISPOSITIVOS[device_type]
            device_name = random.choice(device_names)

            # Generar MAC única usando el índice para evitar duplicados
            mac = f"00:1B:44:11:{(i//256):02X}:{(i%256):02X}"

            device = Device(
                id=str(uuid.uuid4()),
                residence_id=residence.id,
                type=device_type,
                name=f"{device_name} {i+1}",
                mac=mac,  # MAC única
                battery_percent=random.randint(20, 100)
            )

            self.session.add(device)
            devices.append(device)

        await self.session.flush()
        return devices

    async def seed_all(self):
        """Ejecuta todo el proceso de seeding con los volúmenes requeridos"""
        print("🌱 Iniciando seeding de la base de datos con grandes volúmenes...")

        try:
            # 1. Crear superadmin
            print("👤 Creando superadmin...")
            superadmin = await self.create_user("superadmin", "admin123", "superadmin")

            # 2. Crear residencias (28)
            residences = await self.seed_residences(28)

            # 3. Crear gestores (36) y asignarlos a residencias
            managers = await self.seed_managers(36)
            await self.assign_managers_to_residences(managers, residences)

            # 4. Crear profesionales (80) y asignarlos a residencias
            professionals = await self.seed_professionals(80)
            # Asignar profesionales a las mismas residencias que los gestores
            for professional in professionals:
                residence = random.choice(residences)
                assignment = UserResidence(
                    user_id=professional.id,
                    residence_id=residence.id
                )
                self.session.add(assignment)

            # 5. Crear pisos para residencias
            floors_by_residence = await self.create_floors_for_residences(residences)

            # 6. Crear habitaciones (80) asignadas a residencias
            rooms = await self.seed_rooms(80, residences, floors_by_residence)

            # 7. Crear camas para habitaciones
            beds = await self.seed_beds(rooms)

            # 8. Crear residentes (160) asignados a camas
            residents = await self.seed_residents(160, beds, residences)

            # 9. Crear categorías de tareas (18 por residencia)
            categories = await self.seed_task_categories(residences)

            # 10. Crear plantillas de tareas (20 por categoría)
            templates = await self.seed_task_templates(categories)

            # 11. Crear aplicaciones de tareas
            all_users = [superadmin] + managers + professionals
            applications = await self.seed_task_applications(residents, templates, all_users)

            # 12. Crear dispositivos (40 distribuidos)
            devices = await self.seed_devices(40, residences)

            print("💾 Guardando cambios en la base de datos...")
            await self.session.commit()

            print("✅ Seeding completado exitosamente!")
            print(f"📊 Resumen:")
            print(f"   - Residencias: {len(residences)}")
            print(f"   - Gestores: {len(managers)}")
            print(f"   - Profesionales: {len(professionals)}")
            print(f"   - Habitaciones: {len(rooms)}")
            print(f"   - Camas: {len(beds)}")
            print(f"   - Residentes: {len(residents)}")
            print(f"   - Categorías de tareas: {len(categories)}")
            print(f"   - Plantillas de tareas: {len(templates)}")
            print(f"   - Aplicaciones de tareas: {len(applications)}")
            print(f"   - Dispositivos: {len(devices)}")

        except Exception as e:
            print(f"❌ Error durante el seeding: {e}")
            await self.session.rollback()
            raise


async def main():
    """Función principal"""
    async with async_session() as session:
        seeder = EnhancedDataSeeder(session)
        await seeder.seed_all()


if __name__ == "__main__":
    asyncio.run(main())