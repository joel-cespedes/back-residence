#!/usr/bin/env python3
"""
Script para poblar la base de datos con datos realistas de 2 años
para el sistema de gestión de residencias
"""

import asyncio
import random
from datetime import datetime, timedelta, date
from typing import List
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from app.models import Base, User, Residence, Floor, Room, Bed, Resident, Tag, ResidentTag, Device, TaskCategory, TaskTemplate, TaskApplication, Measurement
from app.security import hash_alias, get_password_hash
from app.config import DATABASE_URL

# Configuración de la base de datos
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Datos de ejemplo
NOMBRES_RESIDENTES = [
    "María García", "Juan Rodríguez", "Ana Martínez", "Carlos López", "Lucía Fernández",
    "Miguel González", "Carmen Sánchez", "José Ramírez", "Isabel Torres", "Francisco Díaz",
    "Pilar Jiménez", "Antonio Moreno", "Rosa Muñoz", "Manuel Álvarez", "Teresa Castro",
    "Luis Herrera", "Elena Ortiz", "Javier Ruiz", "Marina Vargas", "Ricardo Molina"
]

APELLIDOS_COMUNES = ["García", "Rodríguez", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Fernández"]

NOMBRES_DISPOSITIVOS = {
    "blood_pressure": ["BP Monitor 001", "BP Monitor 002", "BP Monitor 003", "BP Pro Max"],
    "pulse_oximeter": ["OxiMeter A1", "OxiMeter B2", "Pulse Check Pro", "OxiMax Elite"],
    "scale": ["Smart Scale 1", "Digital Weight Pro", "Health Scale X1", "Precision Scale"],
    "thermometer": ["TempCheck Pro", "Digital Therm 1", "Infrared Temp Pro", "Smart Thermometer"]
}

CATEGORIAS_TAREAS = [
    "Medicación", "Higiene Personal", "Alimentación", "Movilidad",
    "Control Signos Vitales", "Terapia", "Socialización", "Descanso"
]

TEMPLATES_TAREAS = {
    "Medicación": [
        ("Toma matutina de medicamentos", "Tomado", "Parcial", "No tomado", "Rechazado", "Con efectos", "Sin efectos"),
        ("Toma nocturna de medicamentos", "Tomado", "Parcial", "No tomado", "Rechazado", "Con efectos", "Sin efectos"),
        ("Control de presión arterial", "Normal", "Elevada", "Baja", "Crítica", "Controlada", "No controlada")
    ],
    "Higiene Personal": [
        ("Aseo matutino", "Completo", "Parcial", "No realizado", "Rechazado", "Con ayuda", "Independiente"),
        ("Cambio de ropa", "Realizado", "Parcial", "No realizado", "Rechazado", "Con ayuda", "Independiente"),
        ("Higiene bucal", "Completa", "Parcial", "No realizada", "Rechazada", "Con ayuda", "Independiente")
    ],
    "Alimentación": [
        ("Desayuno", "Completo", "Parcial", "No consumido", "Rechazado", "Con ayuda", "Independiente"),
        ("Almuerzo", "Completo", "Parcial", "No consumido", "Rechazado", "Con ayuda", "Independiente"),
        ("Cena", "Completo", "Parcial", "No consumido", "Rechazado", "Con ayuda", "Independiente")
    ],
    "Control Signos Vitales": [
        ("Control de temperatura", "Normal", "Febril", "Hipotermia", "Crítica", "Controlada", "No controlada"),
        ("Control de saturación", "Normal", "Baja", "Muy baja", "Crítica", "Controlada", "No controlada"),
        ("Control de peso", "Estable", "Ganancia", "Pérdida", "Crítica", "Controlada", "No controlada")
    ]
}

TAGS_RESIDENTES = [
    "Diabetes", "Hipertensión", "Demencia", "Movilidad reducida", "Depresión",
    "Insomnio", "Osteoporosis", "Artritis", "Parkinson", "Alzheimer",
    "Cardiopatía", "EPOC", "ACV", "Cáncer", "Renal crónica"
]

class DataSeeder:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.fecha_inicio = datetime.now() - timedelta(days=730)  # 2 años atrás

    async def seed_all(self):
        """Ejecuta todo el proceso de seeding"""
        print("🌱 Iniciando seeding de la base de datos...")

        # 1. Crear usuarios base
        print("👥 Creando usuarios...")
        superadmin = await self.create_user("superadmin", "admin123", "superadmin")
        manager1 = await self.create_user("manager1", "manager123", "manager")
        manager2 = await self.create_user("manager2", "manager123", "manager")
        prof1 = await self.create_user("prof1", "prof123", "professional")
        prof2 = await self.create_user("prof2", "prof123", "professional")
        prof3 = await self.create_user("prof3", "prof123", "professional")

        # Establecer contexto de usuario para los triggers
        await self.set_user_context(superadmin)

        # 2. Crear residencias
        print("🏢 Creando residencias...")
        res1 = await self.create_residence("Residencia Principal", "Calle Mayor 123", superadmin)
        res2 = await self.create_residence("Residencia Norte", "Avenida Libertad 456", superadmin)

        # 3. Asignar usuarios a residencias
        print("🔗 Asignando usuarios a residencias...")
        await self.assign_user_to_residence(manager1, res1)
        await self.assign_user_to_residence(manager2, res2)
        await self.assign_user_to_residence(prof1, res1)
        await self.assign_user_to_residence(prof2, res1)
        await self.assign_user_to_residence(prof3, res2)

        # 4. Crear estructura física
        print("🏗️ Creando estructura física...")
        floors_res1 = await self.create_floors(res1, 3)
        floors_res2 = await self.create_floors(res2, 2)

        rooms_res1 = await self.create_rooms_for_floors(floors_res1, 4)
        rooms_res2 = await self.create_rooms_for_floors(floors_res2, 3)

        beds_res1 = await self.create_beds_for_rooms(rooms_res1, 2)
        beds_res2 = await self.create_beds_for_rooms(rooms_res2, 2)

        # 5. Crear tags
        print("🏷️ Creando tags...")
        tags = await self.create_tags(TAGS_RESIDENTES)

        # 6. Crear residentes
        print("👴 Creando residentes...")
        residentes_res1 = await self.create_residents(res1, beds_res1, 15, tags, superadmin)
        residentes_res2 = await self.create_residents(res2, beds_res2, 10, tags, superadmin)

        # 7. Crear dispositivos
        print("📱 Creando dispositivos...")
        dispositivos_res1 = await self.create_devices(res1, 8, superadmin)
        dispositivos_res2 = await self.create_devices(res2, 5, superadmin)

        # 8. Crear categorías y templates de tareas
        print("📋 Creando sistema de tareas...")
        tareas_res1 = await self.create_task_system(res1, superadmin)
        tareas_res2 = await self.create_task_system(res2, superadmin)

        # 9. Crear mediciones históricas
        print("📊 Creando mediciones históricas...")
        await self.create_historical_measurements(residentes_res1 + residentes_res2,
                                                 dispositivos_res1 + dispositivos_res2,
                                                 [prof1, prof2, prof3])

        # 10. Crear aplicaciones de tareas
        print("✅ Creando aplicaciones de tareas...")
        await self.create_task_applications(residentes_res1 + residentes_res2,
                                           tareas_res1 + tareas_res2,
                                           [manager1, manager2, prof1, prof2, prof3])

        # 11. Simular cambios de estado de residentes para activar triggers
        print("🔄 Simulando cambios de estado...")
        await self.simulate_resident_status_changes(residentes_res1 + residentes_res2, superadmin)

        print("✅ Seeding completado exitosamente!")

    async def set_user_context(self, user: User):
        """Establece el contexto de usuario para los triggers"""
        await self.session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user.id})

    async def create_user(self, alias: str, password: str, role: str) -> User:
        """Crea un usuario"""
        user = User(
            id=str(uuid.uuid4()),
            role=role,
            alias_encrypted=hash_alias(alias),
            alias_hash=hash_alias(alias),
            password_hash=get_password_hash(password),
            email_encrypted=None,
            phone_encrypted=None
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def create_residence(self, name: str, address: str, created_by: User) -> Residence:
        """Crea una residencia"""
        residence = Residence(
            id=str(uuid.uuid4()),
            name=name,
            address=address,
            phone_encrypted=None,
            email_encrypted=None,
            created_by=created_by.id
        )
        self.session.add(residence)
        await self.session.commit()
        await self.session.refresh(residence)
        return residence

    async def assign_user_to_residence(self, user: User, residence: Residence):
        """Asigna un usuario a una residencia"""
        user_residence = UserResidence(
            user_id=user.id,
            residence_id=residence.id
        )
        self.session.add(user_residence)
        await self.session.commit()

    async def create_floors(self, residence: Residence, count: int) -> List[Floor]:
        """Crea pisos para una residencia"""
        floors = []
        for i in range(1, count + 1):
            floor = Floor(
                id=str(uuid.uuid4()),
                residence_id=residence.id,
                name=f"Piso {i}"
            )
            self.session.add(floor)
            floors.append(floor)
        await self.session.commit()
        return floors

    async def create_rooms_for_floors(self, floors: List[Floor], rooms_per_floor: int) -> List[Room]:
        """Crea habitaciones para los pisos"""
        rooms = []
        for floor in floors:
            for i in range(1, rooms_per_floor + 1):
                room = Room(
                    id=str(uuid.uuid4()),
                    residence_id=floor.residence_id,
                    floor_id=floor.id,
                    name=f"Habitación {floor.name.split()[-1]}{i:02d}"
                )
                self.session.add(room)
                rooms.append(room)
        await self.session.commit()
        return rooms

    async def create_beds_for_rooms(self, rooms: List[Room], beds_per_room: int) -> List[Bed]:
        """Crea camas para las habitaciones"""
        beds = []
        for room in rooms:
            for i in range(1, beds_per_room + 1):
                bed = Bed(
                    id=str(uuid.uuid4()),
                    residence_id=room.residence_id,
                    room_id=room.id,
                    name=f"Cama {i}"
                )
                self.session.add(bed)
                beds.append(bed)
        await self.session.commit()
        return beds

    async def create_tags(self, tag_names: List[str]) -> List[Tag]:
        """Crea tags para residentes"""
        tags = []
        for tag_name in tag_names:
            tag = Tag(
                id=str(uuid.uuid4()),
                name=tag_name
            )
            self.session.add(tag)
            tags.append(tag)
        await self.session.commit()
        return tags

    async def create_residents(self, residence: Residence, beds: List[Bed], count: int, tags: List[Tag], created_by: User) -> List[Resident]:
        """Crea residentes para una residencia"""
        residents = []
        available_beds = beds.copy()
        random.shuffle(available_beds)

        # Establecer contexto para los triggers
        await self.set_user_context(created_by)

        for i in range(min(count, len(available_beds))):
            # Generar fecha de nacimiento realista (65-95 años)
            age = random.randint(65, 95)
            birth_year = datetime.now().year - age
            birth_date = date(birth_year, random.randint(1, 12), random.randint(1, 28))

            # Generar nombre completo
            full_name = random.choice(NOMBRES_RESIDENTES)

            resident = Resident(
                id=str(uuid.uuid4()),
                residence_id=residence.id,
                full_name=full_name,
                birth_date=birth_date,
                sex=random.choice(["Masculino", "Femenino"]),
                gender=random.choice(["Hombre", "Mujer", "Otro"]),
                comments=f"Residente creado automáticamente el {datetime.now().strftime('%Y-%m-%d')}",
                status=random.choice(["active", "active", "active"]),  # Mayormente activos
                bed_id=available_beds[i].id if random.random() > 0.1 else None,  # 90% con cama
                created_by=created_by.id,
            )
            self.session.add(resident)
            residents.append(resident)

            # Asignar tags aleatorios
            num_tags = random.randint(1, 4)
            selected_tags = random.sample(tags, num_tags)
            for tag in selected_tags:
                resident_tag = ResidentTag(
                    resident_id=resident.id,
                    tag_id=tag.id,
                    assigned_by=created_by.id
                )
                self.session.add(resident_tag)

        await self.session.commit()
        return residents

    async def create_devices(self, residence: Residence, count: int, created_by: User) -> List[Device]:
        """Crea dispositivos para una residencia"""
        devices = []
        device_types = list(NOMBRES_DISPOSITIVOS.keys())

        for i in range(count):
            device_type = random.choice(device_types)
            device_names = NOMBRES_DISPOSITIVOS[device_type]

            device = Device(
                id=str(uuid.uuid4()),
                residence_id=residence.id,
                type=device_type,
                name=f"{random.choice(device_names)} {i+1:02d}",
                mac=f"00:11:22:33:44:{i+1:02x}",
                battery_percent=random.randint(20, 100),
                created_by=created_by.id
            )
            self.session.add(device)
            devices.append(device)

        await self.session.commit()
        return devices

    async def create_task_system(self, residence: Residence, created_by: User) -> List[TaskTemplate]:
        """Crea el sistema de tareas para una residencia"""
        categories = []
        templates = []

        # Crear categorías
        for cat_name in CATEGORIAS_TAREAS:
            category = TaskCategory(
                id=str(uuid.uuid4()),
                residence_id=residence.id,
                name=cat_name,
                created_by=created_by.id
            )
            self.session.add(category)
            categories.append(category)

        await self.session.commit()

        # Crear templates
        for category in categories:
            if category.name in TEMPLATES_TAREAS:
                for template_data in TEMPLATES_TAREAS[category.name]:
                    template = TaskTemplate(
                        id=str(uuid.uuid4()),
                        residence_id=residence.id,
                        task_category_id=category.id,
                        name=template_data[0],
                        status1=template_data[1],
                        status2=template_data[2],
                        status3=template_data[3],
                        status4=template_data[4],
                        status5=template_data[5],
                        status6=template_data[6],
                        is_block=random.choice([True, False]),
                        created_by=created_by.id
                    )
                    self.session.add(template)
                    templates.append(template)

        await self.session.commit()
        return templates

    async def create_historical_measurements(self, residents: List[Resident], devices: List[Device], professionals: List[User]):
        """Crea mediciones históricas de los últimos 2 años"""

        for resident in residents:
            # Establecer contexto para un profesional aleatorio
            professional = random.choice(professionals)
            await self.set_user_context(professional)
            # Determinar frecuencia de mediciones basada en condición del residente
            has_diabetes = any(tag.name == "Diabetes" for tag in resident.tags if hasattr(tag, 'name'))
            has_hypertension = any(tag.name == "Hipertensión" for tag in resident.tags if hasattr(tag, 'name'))

            # Generar mediciones para cada día
            current_date = self.fecha_inicio.date()
            end_date = datetime.now().date()

            while current_date <= end_date:
                # Saltar algunos días aleatoriamente
                if random.random() > 0.8:
                    current_date += timedelta(days=1)
                    continue

                # Mediciones por día
                measurements_per_day = random.randint(1, 4)

                for _ in range(measurements_per_day):
                    measurement_type = random.choice(["bp", "weight", "temperature", "spo2"])
                    source = random.choice(["manual", "device"])
                    recorded_by = random.choice(professionals)
                    device = random.choice(devices) if source == "device" else None

                    # Hora aleatoria del día
                    hour = random.randint(6, 22)
                    minute = random.randint(0, 59)
                    taken_at = datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=minute))

                    measurement = Measurement(
                        id=str(uuid.uuid4()),
                        residence_id=resident.residence_id,
                        resident_id=resident.id,
                        recorded_by=recorded_by.id,
                        source=source,
                        device_id=device.id if device else None,
                        type=measurement_type,
                        taken_at=taken_at
                    )

                    # Valores según tipo
                    if measurement_type == "bp":
                        measurement.systolic = random.randint(90, 180)
                        measurement.diastolic = random.randint(60, 110)
                        measurement.pulse_bpm = random.randint(60, 100)
                    elif measurement_type == "spo2":
                        measurement.spo2 = random.randint(88, 100)
                        measurement.pulse_bpm = random.randint(60, 100)
                    elif measurement_type == "weight":
                        measurement.weight_kg = round(random.uniform(45.0, 95.0), 1)
                    elif measurement_type == "temperature":
                        measurement.temperature_c = random.randint(35, 39)

                    self.session.add(measurement)

                current_date += timedelta(days=1)

            # Progresar para evitar transacción muy grande
            if random.random() < 0.1:  # 10% de chance de commit
                await self.session.commit()

        await self.session.commit()

    async def create_task_applications(self, residents: List[Resident], templates: List[TaskTemplate], users: List[User]):
        """Crea aplicaciones de tareas históricas"""

        current_date = self.fecha_inicio.date()
        end_date = datetime.now().date()

        while current_date <= end_date:
            for resident in residents:
                # Establecer contexto para un usuario aleatorio
                user = random.choice(users)
                await self.set_user_context(user)
                # Aplicar tareas aleatorias cada día
                if random.random() > 0.3:  # 70% de chance de tener tareas
                    num_tasks = random.randint(1, 3)
                    selected_templates = random.sample(templates, min(num_tasks, len(templates)))

                    for template in selected_templates:
                        applied_by = random.choice(users)

                        task_app = TaskApplication(
                            id=str(uuid.uuid4()),
                            residence_id=resident.residence_id,
                            resident_id=resident.id,
                            task_template_id=template.id,
                            applied_by=applied_by.id,
                            applied_at=datetime.combine(current_date, datetime.min.time().replace(hour=9, minute=0))
                        )

                        # 70% de chance de tener estado completado
                        if random.random() > 0.3:
                            status_index = random.randint(1, 4)  # Usar primeros 4 estados
                            task_app.selected_status_index = status_index

                        self.session.add(task_app)

            current_date += timedelta(days=1)

            # Commit periódico
            if random.random() < 0.05:  # 5% de chance de commit
                await self.session.commit()

        await self.session.commit()

    async def simulate_resident_status_changes(self, residents: List[Resident], user: User):
        """Simula cambios de estado de residentes para activar triggers"""
        await self.set_user_context(user)

        # Cambiar algunos residentes a discharged (5%)
        discharged_count = int(len(residents) * 0.05)
        selected_discharged = random.sample(residents, discharged_count)

        for resident in selected_discharged:
            resident.status = "discharged"
            await self.session.commit()

            # Crear algunas actualizaciones adicionales para generar más eventos
            await self.session.refresh(resident)

        # Cambiar algunos residentes a deceased (1%)
        deceased_count = int(len(residents) * 0.01)
        available_residents = [r for r in residents if r.status == "active"]
        if available_residents and deceased_count > 0:
            selected_deceased = random.sample(available_residents, min(deceased_count, len(available_residents)))
            for resident in selected_deceased:
                resident.status = "deceased"
                await self.session.commit()
                await self.session.refresh(resident)

        print(f"✅ Simulados {discharged_count} cambios a discharged y {len(selected_deceased) if 'selected_deceased' in locals() else 0} cambios a deceased")

async def main():
    """Función principal para ejecutar el seeding"""
    async with async_session() as session:
        # Verificar si ya hay datos
        result = await session.execute(select(Residence).limit(1))
        if result.scalar_one_or_none():
            print("⚠️ La base de datos ya contiene datos. ¿Desea continuar? (y/N)")
            if input().lower() != 'y':
                print("Operación cancelada.")
                return

        seeder = DataSeeder(session)
        await seeder.seed_all()

if __name__ == "__main__":
    asyncio.run(main())