# app/models.py
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, BYTEA, ENUM, JSONB
from sqlalchemy import Text, Integer, SmallInteger, Boolean, ForeignKey, Date, DateTime, func
from datetime import datetime, date
from typing import Optional, Dict

# ---------- Base ----------
class Base(DeclarativeBase):
    pass

# ---------- Enums ya creados en BD (no crear tipos) ----------
user_role_enum          = ENUM('superadmin', 'manager', 'professional', name='user_role_enum', create_type=False)
resident_status_enum    = ENUM('active', 'discharged', 'deceased',     name='resident_status_enum', create_type=False)
device_type_enum        = ENUM('blood_pressure','pulse_oximeter','scale','thermometer', name='device_type_enum', create_type=False)
measurement_type_enum   = ENUM('bp','spo2','weight','temperature',     name='measurement_type_enum', create_type=False)
measurement_source_enum = ENUM('device','voice','manual',              name='measurement_source_enum', create_type=False)

# Nota: usamos UUID(as_uuid=False) para mapear como str. Si prefieres uuid.UUID, usa as_uuid=True y anota con uuid.UUID.

# ---------- Tablas ----------
class User(Base):
    __tablename__ = "user"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    role: Mapped[str] = mapped_column(user_role_enum, nullable=False)
    alias_encrypted: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    alias_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

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

class UserResidence(Base):
    __tablename__ = "user_residence"
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="CASCADE"), primary_key=True)

class Floor(Base):
    __tablename__ = "floor"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class Room(Base):
    __tablename__ = "room"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    floor_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("floor.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class Bed(Base):
    __tablename__ = "bed"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    room_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("room.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class Resident(Base):
    __tablename__ = "resident"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[Optional[str]] = mapped_column(Text)
    gender: Mapped[Optional[str]] = mapped_column(Text)
    comments: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(resident_status_enum, server_default='active', nullable=False)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bed_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("bed.id", ondelete="SET NULL"))
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Tag(Base):
    __tablename__ = "tag"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class ResidentTag(Base):
    __tablename__ = "resident_tag"
    resident_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("resident.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tag.id", ondelete="RESTRICT"), primary_key=True)
    assigned_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Device(Base):
    __tablename__ = "device"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    type: Mapped[str] = mapped_column(device_type_enum, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mac: Mapped[str] = mapped_column(Text, nullable=False)
    battery_percent: Mapped[Optional[int]] = mapped_column(SmallInteger)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class TaskCategory(Base):
    __tablename__ = "task_category"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class TaskTemplate(Base):
    __tablename__ = "task_template"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    task_category_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("task_category.id", ondelete="RESTRICT"), nullable=False)
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

class TaskApplication(Base):
    __tablename__ = "task_application"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    resident_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("resident.id", ondelete="RESTRICT"), nullable=False)
    task_template_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("task_template.id", ondelete="RESTRICT"), nullable=False)
    applied_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    selected_status_index: Mapped[Optional[int]] = mapped_column(SmallInteger)
    selected_status_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class Measurement(Base):
    __tablename__ = "measurement"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id", ondelete="RESTRICT"), nullable=False)
    resident_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("resident.id", ondelete="RESTRICT"), nullable=False)
    recorded_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"), nullable=False)
    source: Mapped[str] = mapped_column(measurement_source_enum, nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("device.id"))
    type: Mapped[str] = mapped_column(measurement_type_enum, nullable=False)

    systolic: Mapped[Optional[int]]
    diastolic: Mapped[Optional[int]]
    pulse_bpm: Mapped[Optional[int]]
    spo2: Mapped[Optional[int]]
    weight_kg: Mapped[Optional[float]]
    temperature_c: Mapped[Optional[int]]

    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

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
