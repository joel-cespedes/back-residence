
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, BYTEA, ENUM, JSONB
from sqlalchemy import Text, Integer, SmallInteger, Boolean, ForeignKey, Date, DateTime, func
from datetime import datetime, date
from typing import Optional, Dict

class Base(DeclarativeBase):
    pass

user_role_enum = ENUM(
    'superadmin', 'manager', 'professional',
    name='user_role_enum',
    create_type=False
)

resident_status_enum = ENUM(
    'active', 'discharged', 'deceased',
    name='resident_status_enum',
    create_type=False
)

device_type_enum = ENUM(
    'blood_pressure', 'pulse_oximeter', 'scale', 'thermometer',
    name='device_type_enum',
    create_type=False
)

measurement_type_enum = ENUM(
    'bp', 'spo2', 'weight', 'temperature',
    name='measurement_type_enum',
    create_type=False
)

measurement_source_enum = ENUM(
    'device', 'voice', 'manual',
    name='measurement_source_enum',
    create_type=False
)

class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    role: Mapped[str] = mapped_column(user_role_enum, nullable=False)
    alias_encrypted: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    alias_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text)
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<User(id={self.id[:8]}..., role={self.role})>"

    def __str__(self) -> str:
        return f"Usuario {self.alias_hash[:8]}... ({self.role})"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    @property
    def contact_info(self) -> dict:
        return {
            "email_encrypted": self.email_encrypted,
            "phone_encrypted": self.phone_encrypted
        }

class Residence(Base):
    __tablename__ = "residence"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Residence(id={self.id[:8]}..., name={self.name})>"

    def __str__(self) -> str:
        return f"Residencia {self.name}"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    @property
    def contact_info(self) -> dict:
        return {
            "phone_encrypted": self.phone_encrypted,
            "email_encrypted": self.email_encrypted
        }

class UserResidence(Base):
    __tablename__ = "user_residence"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True
    )
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="CASCADE"),
        primary_key=True
    )

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<UserResidence(user_id={self.user_id[:8]}..., residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Asignación: Usuario {self.user_id[:8]}... → Residencia {self.residence_id[:8]}..."


class Floor(Base):
    __tablename__ = "floor"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Floor(id={self.id[:8]}..., name={self.name}, residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Piso {self.name}"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

class Room(Base):
    __tablename__ = "room"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    floor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("floor.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Room(id={self.id[:8]}..., name={self.name}, floor_id={self.floor_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Habitación {self.name}"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

class Bed(Base):
    __tablename__ = "bed"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    room_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("room.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Bed(id={self.id[:8]}..., name={self.name}, room_id={self.room_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Cama {self.name}"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    @property
    def is_occupied(self) -> bool:
        return False


class Resident(Base):
    __tablename__ = "resident"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )

    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[Optional[str]] = mapped_column(Text)
    comments: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        resident_status_enum,
        server_default='active',
        nullable=False
    )
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bed_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("bed.id", ondelete="SET NULL")
    )
    room_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("room.id", ondelete="SET NULL")
    )
    floor_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("floor.id", ondelete="SET NULL")
    )

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Resident(id={self.id[:8]}..., name={self.full_name}, status={self.status})>"

    def __str__(self) -> str:
        return f"Residente {self.full_name} ({self.status})"

    @property
    def age(self) -> Optional[int]:
        if not self.birth_date:
            return None

        today = date.today()
        age = today.year - self.birth_date.year

        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age -= 1

        return age

    @property
    def is_active(self) -> bool:
        return self.status == 'active' and self.deleted_at is None

    @property
    def is_discharged(self) -> bool:
        return self.status == 'discharged'

    @property
    def is_deceased(self) -> bool:
        return self.status == 'deceased'

    @property
    def is_assigned_to_bed(self) -> bool:
        return self.bed_id is not None

    @property
    def personal_info(self) -> dict:
        return {
            "full_name": self.full_name,
            "birth_date": self.birth_date,
            "age": self.age,
            "sex": self.sex,
            "comments": self.comments
        }

    @property
    def location_info(self) -> dict:
        return {
            "residence_id": self.residence_id,
            "bed_id": self.bed_id,
            "is_assigned": self.is_assigned_to_bed
        }


class Device(Base):
    __tablename__ = "device"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )

    type: Mapped[str] = mapped_column(device_type_enum, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mac: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    battery_percent: Mapped[Optional[int]] = mapped_column(SmallInteger)

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Device(id={self.id[:8]}..., name={self.name}, type={self.type}, mac={self.mac})>"

    def __str__(self) -> str:
        return f"Dispositivo {self.name} ({self.type})"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    @property
    def battery_status(self) -> str:
        if self.battery_percent is None:
            return "Desconocido"

        if self.battery_percent >= 80:
            return "Excelente"
        elif self.battery_percent >= 50:
            return "Bueno"
        elif self.battery_percent >= 20:
            return "Bajo"
        else:
            return "Crítico"

    @property
    def is_low_battery(self) -> bool:
        return self.battery_percent is not None and self.battery_percent < 20

    @property
    def needs_maintenance(self) -> bool:
        return self.is_low_battery

    @property
    def device_info(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "mac": self.mac,
            "battery_percent": self.battery_percent,
            "battery_status": self.battery_status,
            "is_low_battery": self.is_low_battery,
            "needs_maintenance": self.needs_maintenance,
            "residence_id": self.residence_id,
            "is_active": self.is_active
        }

    @property
    def human_readable_type(self) -> str:
        type_map = {
            "blood_pressure": "Tensiómetro",
            "pulse_oximeter": "Pulsioxímetro",
            "scale": "Báscula",
            "thermometer": "Termómetro"
        }
        return type_map.get(self.type, self.type)


class Measurement(Base):
    __tablename__ = "measurement"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    resident_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("resident.id", ondelete="RESTRICT"),
        nullable=False
    )

    recorded_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False
    )
    source: Mapped[str] = mapped_column(measurement_source_enum, nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("device.id")
    )
    type: Mapped[str] = mapped_column(measurement_type_enum, nullable=False)

    systolic: Mapped[Optional[int]]
    diastolic: Mapped[Optional[int]]

    pulse_bpm: Mapped[Optional[int]]
    spo2: Mapped[Optional[int]]

    weight_kg: Mapped[Optional[float]]
    temperature_c: Mapped[Optional[float]]

    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Measurement(id={self.id[:8]}..., type={self.type}, resident_id={self.resident_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Medición de {self.type} para residente {self.resident_id[:8]}..."

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    @property
    def measurement_values(self) -> dict:
        values = {
            "type": self.type,
            "source": self.source,
            "taken_at": self.taken_at,
            "device_id": self.device_id
        }

        if self.type == "bp":
            values.update({
                "systolic": self.systolic,
                "diastolic": self.diastolic,
                "pulse": self.pulse_bpm
            })
        elif self.type == "spo2":
            values.update({
                "spo2": self.spo2,
                "pulse": self.pulse_bpm
            })
        elif self.type == "weight":
            values.update({
                "weight_kg": self.weight_kg
            })
        elif self.type == "temperature":
            values.update({
                "temperature_c": self.temperature_c
            })

        return values

    @property
    def human_readable_type(self) -> str:
        type_map = {
            "bp": "Presión arterial",
            "spo2": "Saturación de oxígeno",
            "weight": "Peso",
            "temperature": "Temperatura"
        }
        return type_map.get(self.type, self.type)

    @property
    def human_readable_source(self) -> str:
        source_map = {
            "device": "Dispositivo",
            "voice": "Voz",
            "manual": "Manual"
        }
        return source_map.get(self.source, self.source)

    @property
    def is_normal(self) -> Optional[bool]:
        if self.type == "bp" and self.systolic and self.diastolic:
            return (90 <= self.systolic <= 120) and (60 <= self.diastolic <= 80)
        elif self.type == "spo2" and self.spo2:
            return self.spo2 >= 95
        elif self.type == "temperature" and self.temperature_c:
            return 36 <= self.temperature_c <= 37.5

        return None

    @property
    def formatted_value(self) -> str:
        if self.type == "bp" and self.systolic and self.diastolic:
            return f"{self.systolic}/{self.diastolic} mmHg"
        elif self.type == "spo2" and self.spo2:
            return f"{self.spo2}%"
        elif self.type == "weight" and self.weight_kg:
            return f"{self.weight_kg} kg"
        elif self.type == "temperature" and self.temperature_c:
            return f"{self.temperature_c}°C"
        else:
            return "N/A"


class TaskCategory(Base):
    __tablename__ = "task_category"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<TaskCategory(id={self.id[:8]}..., name={self.name}, residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Categoría: {self.name}"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

class TaskTemplate(Base):
    __tablename__ = "task_template"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    task_category_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("task_category.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    status1: Mapped[Optional[str]] = mapped_column(Text)
    status2: Mapped[Optional[str]] = mapped_column(Text)
    status3: Mapped[Optional[str]] = mapped_column(Text)
    status4: Mapped[Optional[str]] = mapped_column(Text)
    status5: Mapped[Optional[str]] = mapped_column(Text)
    status6: Mapped[Optional[str]] = mapped_column(Text)

    audio_phrase: Mapped[Optional[str]] = mapped_column(Text)
    is_block: Mapped[Optional[bool]] = mapped_column(Boolean)

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<TaskTemplate(id={self.id[:8]}..., name={self.name}, category_id={self.task_category_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Plantilla: {self.name}"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    @property
    def available_statuses(self) -> list[str]:
        statuses = []
        for i in range(1, 7):
            status = getattr(self, f"status{i}", None)
            if status:
                statuses.append(status)
        return statuses

class TaskApplication(Base):
    __tablename__ = "task_application"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    resident_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("resident.id", ondelete="RESTRICT"),
        nullable=False
    )
    task_template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("task_template.id", ondelete="RESTRICT"),
        nullable=False
    )

    applied_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    selected_status_index: Mapped[Optional[int]] = mapped_column(SmallInteger)
    selected_status_text: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<TaskApplication(id={self.id[:8]}..., resident_id={self.resident_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Tarea aplicada a residente {self.resident_id[:8]}..."

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    @property
    def current_status(self) -> Optional[str]:
        return self.selected_status_text

    @property
    def is_completed(self) -> bool:
        return self.selected_status_text is not None


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)

    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Tag(id={self.id[:8]}..., name={self.name})>"

    def __str__(self) -> str:
        return f"Etiqueta: {self.name}"

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

class ResidentTag(Base):
    __tablename__ = "resident_tag"

    resident_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("resident.id", ondelete="CASCADE"),
        primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tag.id", ondelete="RESTRICT"),
        primary_key=True
    )

    assigned_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<ResidentTag(resident_id={self.resident_id[:8]}..., tag_id={self.tag_id[:8]}...)>"

    def __str__(self) -> str:
        return f"Etiqueta {self.tag_id[:8]}... asignada a residente {self.resident_id[:8]}..."

    @property
    def assignment_info(self) -> dict:
        return {
            "resident_id": self.resident_id,
            "tag_id": self.tag_id,
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at
        }


class EventLog(Base):
    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    actor_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    residence_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id"))

    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    action: Mapped[str] = mapped_column(Text, nullable=False)

    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    meta: Mapped[Optional[Dict]] = mapped_column(JSONB)

    def __repr__(self) -> str:
        return f"<EventLog(id={self.id}, action={self.action}, entity={self.entity})>"

    def __str__(self) -> str:
        actor_info = f"Usuario {self.actor_user_id[:8]}..." if self.actor_user_id else "Sistema"
        return f"{actor_info} {self.action} {self.entity}"

    @property
    def event_info(self) -> dict:
        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "residence_id": self.residence_id,
            "entity": self.entity,
            "entity_id": self.entity_id,
            "action": self.action,
            "at": self.at,
            "meta": self.meta
        }

    @property
    def human_readable_action(self) -> str:
        action_map = {
            "create": "creó",
            "update": "actualizó",
            "delete": "eliminó",
            "read": "consultó",
            "login": "inició sesión",
            "logout": "cerró sesión",
            "assign": "asignó",
            "unassign": "desasignó",
            "approve": "aprobó",
            "reject": "rechazó",
            "complete": "completó",
            "cancel": "canceló"
        }
        return action_map.get(self.action, self.action)

    @property
    def human_readable_entity(self) -> str:
        entity_map = {
            "user": "usuario",
            "resident": "residente",
            "residence": "residencia",
            "floor": "piso",
            "room": "habitación",
            "bed": "cama",
            "device": "dispositivo",
            "task": "tarea",
            "measurement": "medición",
            "tag": "etiqueta"
        }
        return entity_map.get(self.entity, self.entity)

    @property
    def formatted_description(self) -> str:
        actor = f"Usuario {self.actor_user_id[:8]}..." if self.actor_user_id else "Sistema"
        action = self.human_readable_action
        entity = self.human_readable_entity

        description = f"{actor} {action} {entity}"

        if self.entity_id:
            description += f" (ID: {self.entity_id[:8]}...)"

        if self.residence_id:
            description += f" en residencia {self.residence_id[:8]}..."

        return description

    @property
    def is_system_event(self) -> bool:
        return self.actor_user_id is None

    @property
    def is_security_related(self) -> bool:
        security_actions = {"login", "logout", "create", "delete", "update"}
        security_entities = {"user", "residence"}
        return self.action in security_actions or self.entity in security_entities

    @property
    def event_age(self) -> Optional[datetime.timedelta]:
        if self.at:
            return datetime.now(self.at.tzinfo) - self.at
        return None


__all__ = [
    "Base",
    "user_role_enum",
    "resident_status_enum", 
    "device_type_enum",
    "measurement_type_enum",
    "measurement_source_enum",

    "User",
    "Residence",
    "UserResidence",
    "Floor",
    "Room", 
    "Bed",
    "Resident",
    "Device",
    "TaskCategory",
    "TaskTemplate",
    "TaskApplication",
    "Measurement",
    "Tag",
    "ResidentTag",
    "EventLog",
]
