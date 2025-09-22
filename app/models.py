# =====================================================================
# MODELOS DE BASE DE DATOS DEL SISTEMA DE RESIDENCIAS
# =====================================================================
"""
Modelos de base de datos para el sistema de gestión de residencias.
Todos los modelos están organizados por entidad en un solo archivo para mantener
coherencia y facilitar el mantenimiento.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, BYTEA, ENUM, JSONB
from sqlalchemy import Text, Integer, SmallInteger, Boolean, ForeignKey, Date, DateTime, func
from datetime import datetime, date
from typing import Optional, Dict

# =====================================================================
# CLASE BASE Y ENUMERACIONES
# =====================================================================

class Base(DeclarativeBase):
    """
    Clase base declarativa para todos los modelos de SQLAlchemy.
    Proporciona funcionalidad común a todas las entidades.
    """
    pass

# ---------- Enumeraciones definidas en la base de datos ----------
# Nota: Estos enums ya existen en la BD, no se crean tipos nuevos

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

# =====================================================================
# MODELO DE USUARIOS
# =====================================================================

class User(Base):
    """
    Modelo de Usuario para el sistema de residencias.
    Representa a los usuarios del sistema con diferentes roles y permisos.
    """
    __tablename__ = "user"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    role: Mapped[str] = mapped_column(user_role_enum, nullable=False)

    # ---------- Datos de autenticación ----------
    alias_encrypted: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    alias_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    
    # ---------- Datos personales ----------
    name: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Contacto (encriptado) ----------
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string del usuario."""
        return f"<User(id={self.id[:8]}..., role={self.role})>"

    def __str__(self) -> str:
        """Representación legible del usuario."""
        return f"Usuario {self.alias_hash[:8]}... ({self.role})"

    @property
    def is_active(self) -> bool:
        """
        Verifica si el usuario está activo.
        Un usuario está activo si no ha sido eliminado (soft delete).
        """
        return self.deleted_at is None

    @property
    def contact_info(self) -> dict:
        """
        Devuelve un diccionario con la información de contacto.
        Note: Los campos están encriptados, requieren desencriptación.
        """
        return {
            "email_encrypted": self.email_encrypted,
            "phone_encrypted": self.phone_encrypted
        }

# =====================================================================
# MODELO DE RESIDENCIAS
# =====================================================================

class Residence(Base):
    """
    Modelo de Residencia para el sistema de gestión de residencias.
    Representa una residencia donde viven los residentes y trabajan los profesionales.
    """
    __tablename__ = "residence"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Contacto (encriptado) ----------
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la residencia."""
        return f"<Residence(id={self.id[:8]}..., name={self.name})>"

    def __str__(self) -> str:
        """Representación legible de la residencia."""
        return f"Residencia {self.name}"

    @property
    def is_active(self) -> bool:
        """
        Verifica si la residencia está activa.
        Una residencia está activa si no ha sido eliminada (soft delete).
        """
        return self.deleted_at is None

    @property
    def contact_info(self) -> dict:
        """
        Devuelve un diccionario con la información de contacto.
        Note: Los campos están encriptados, requieren desencriptación.
        """
        return {
            "phone_encrypted": self.phone_encrypted,
            "email_encrypted": self.email_encrypted
        }

class UserResidence(Base):
    """
    Modelo de relación entre Usuarios y Residencias.
    Tabla de asociación que define qué usuarios tienen acceso a qué residencias.
    """
    __tablename__ = "user_residence"

    # ---------- Claves primarias compuestas ----------
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

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la relación usuario-residencia."""
        return f"<UserResidence(user_id={self.user_id[:8]}..., residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la relación usuario-residencia."""
        return f"Asignación: Usuario {self.user_id[:8]}... → Residencia {self.residence_id[:8]}..."

# =====================================================================
# MODELOS DE UBICACIÓN (PISOS, HABITACIONES, CAMAS)
# =====================================================================

class Floor(Base):
    """
    Modelo de Piso para la estructura jerárquica de residencias.
    Representa un piso dentro de una residencia.
    """
    __tablename__ = "floor"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string del piso."""
        return f"<Floor(id={self.id[:8]}..., name={self.name}, residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible del piso."""
        return f"Piso {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si el piso está activo (no eliminado)."""
        return self.deleted_at is None

class Room(Base):
    """
    Modelo de Habitación para la estructura jerárquica de residencias.
    Representa una habitación dentro de un piso.
    """
    __tablename__ = "room"

    # ---------- Identificación ----------
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

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la habitación."""
        return f"<Room(id={self.id[:8]}..., name={self.name}, floor_id={self.floor_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la habitación."""
        return f"Habitación {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la habitación está activa (no eliminada)."""
        return self.deleted_at is None

class Bed(Base):
    """
    Modelo de Cama para la estructura jerárquica de residencias.
    Representa una cama dentro de una habitación donde se alojan los residentes.
    """
    __tablename__ = "bed"

    # ---------- Identificación ----------
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

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la cama."""
        return f"<Bed(id={self.id[:8]}..., name={self.name}, room_id={self.room_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la cama."""
        return f"Cama {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la cama está activa (no eliminada)."""
        return self.deleted_at is None

    @property
    def is_occupied(self) -> bool:
        """
        Verifica si la cama está ocupada por un residente.
        Esta propiedad requiere una consulta a la base de datos para verificar
        si hay un residente asignado actualmente.
        """
        # Esta propiedad se implementaría con una consulta a la base de datos
        # Por ahora, devuelve False como valor por defecto
        return False

# =====================================================================
# MODELO DE RESIDENTES
# =====================================================================

class Resident(Base):
    """
    Modelo de Residente para el sistema de gestión de residencias.
    Representa a las personas que viven en las residencias y reciben cuidados.
    """
    __tablename__ = "resident"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )

    # ---------- Datos personales ----------
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[Optional[str]] = mapped_column(Text)
    comments: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Estado y asignación ----------
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

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---------- Soft delete ----------
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string del residente."""
        return f"<Resident(id={self.id[:8]}..., name={self.full_name}, status={self.status})>"

    def __str__(self) -> str:
        """Representación legible del residente."""
        return f"Residente {self.full_name} ({self.status})"

    @property
    def age(self) -> Optional[int]:
        """
        Calcula la edad del residente basado en su fecha de nacimiento.
        Returns:
            int: Edad del residente o None si no tiene fecha de nacimiento
        """
        if not self.birth_date:
            return None

        today = date.today()
        age = today.year - self.birth_date.year

        # Ajustar si el cumpleaños aún no ha pasado este año
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age -= 1

        return age

    @property
    def is_active(self) -> bool:
        """
        Verifica si el residente está activo.
        Un residente está activo si su estado es 'active' y no ha sido eliminado.
        """
        return self.status == 'active' and self.deleted_at is None

    @property
    def is_discharged(self) -> bool:
        """Verifica si el residente ha sido dado de alta."""
        return self.status == 'discharged'

    @property
    def is_deceased(self) -> bool:
        """Verifica si el residente ha fallecido."""
        return self.status == 'deceased'

    @property
    def is_assigned_to_bed(self) -> bool:
        """
        Verifica si el residente tiene una cama asignada.
        """
        return self.bed_id is not None

    @property
    def personal_info(self) -> dict:
        """
        Devuelve un diccionario con la información personal del residente.
        """
        return {
            "full_name": self.full_name,
            "birth_date": self.birth_date,
            "age": self.age,
            "sex": self.sex,
            "comments": self.comments
        }

    @property
    def location_info(self) -> dict:
        """
        Devuelve un diccionario con la información de ubicación del residente.
        """
        return {
            "residence_id": self.residence_id,
            "bed_id": self.bed_id,
            "is_assigned": self.is_assigned_to_bed
        }

# =====================================================================
# MODELO DE DISPOSITIVOS MÉDICOS
# =====================================================================

class Device(Base):
    """
    Modelo de Dispositivo médico para el sistema de residencias.
    Representa los dispositivos médicos utilizados para tomar mediciones de los residentes.
    """
    __tablename__ = "device"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )

    # ---------- Información del dispositivo ----------
    type: Mapped[str] = mapped_column(device_type_enum, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mac: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # ---------- Estado del dispositivo ----------
    battery_percent: Mapped[Optional[int]] = mapped_column(SmallInteger)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string del dispositivo."""
        return f"<Device(id={self.id[:8]}..., name={self.name}, type={self.type}, mac={self.mac})>"

    def __str__(self) -> str:
        """Representación legible del dispositivo."""
        return f"Dispositivo {self.name} ({self.type})"

    @property
    def is_active(self) -> bool:
        """
        Verifica si el dispositivo está activo.
        Un dispositivo está activo si no ha sido eliminado (soft delete).
        """
        return self.deleted_at is None

    @property
    def battery_status(self) -> str:
        """
        Devuelve una descripción del estado de la batería.
        Returns:
            str: Descripción del nivel de batería
        """
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
        """
        Verifica si la batería está baja (menos de 20%).
        Returns:
            bool: True si la batería está baja, False en caso contrario
        """
        return self.battery_percent is not None and self.battery_percent < 20

    @property
    def needs_maintenance(self) -> bool:
        """
        Verifica si el dispositivo necesita mantenimiento.
        Considera que necesita mantenimiento si la batería está baja.
        Returns:
            bool: True si necesita mantenimiento, False en caso contrario
        """
        return self.is_low_battery

    @property
    def device_info(self) -> dict:
        """
        Devuelve un diccionario con la información completa del dispositivo.
        Returns:
            dict: Información del dispositivo incluyendo estado de batería
        """
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
        """
        Devuelve una descripción legible del tipo de dispositivo.
        Returns:
            str: Descripción del tipo de dispositivo en español
        """
        type_map = {
            "blood_pressure": "Tensiómetro",
            "pulse_oximeter": "Pulsioxímetro",
            "scale": "Báscula",
            "thermometer": "Termómetro"
        }
        return type_map.get(self.type, self.type)

# =====================================================================
# MODELO DE MEDICIONES MÉDICAS
# =====================================================================

class Measurement(Base):
    """
    Modelo de Medición para el sistema de residencias.
    Representa las mediciones médicas tomadas a los residentes.
    """
    __tablename__ = "measurement"

    # ---------- Identificación ----------
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

    # ---------- Información de la medición ----------
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

    # ---------- Valores de medición ----------
    # Presión arterial
    systolic: Mapped[Optional[int]]
    diastolic: Mapped[Optional[int]]

    # Signos vitales
    pulse_bpm: Mapped[Optional[int]]
    spo2: Mapped[Optional[int]]

    # Otros
    weight_kg: Mapped[Optional[float]]
    temperature_c: Mapped[Optional[int]]

    # ---------- Timestamps ----------
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---------- Soft delete ----------
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la medición."""
        return f"<Measurement(id={self.id[:8]}..., type={self.type}, resident_id={self.resident_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la medición."""
        return f"Medición de {self.type} para residente {self.resident_id[:8]}..."

    @property
    def is_active(self) -> bool:
        """Verifica si la medición está activa (no eliminada)."""
        return self.deleted_at is None

    @property
    def measurement_values(self) -> dict:
        """
        Devuelve un diccionario con los valores de la medición según el tipo.
        Returns:
            dict: Valores relevantes según el tipo de medición
        """
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
        """
        Devuelve una descripción legible del tipo de medición.
        Returns:
            str: Descripción del tipo de medición en español
        """
        type_map = {
            "bp": "Presión arterial",
            "spo2": "Saturación de oxígeno",
            "weight": "Peso",
            "temperature": "Temperatura"
        }
        return type_map.get(self.type, self.type)

    @property
    def human_readable_source(self) -> str:
        """
        Devuelve una descripción legible de la fuente de la medición.
        Returns:
            str: Descripción de la fuente en español
        """
        source_map = {
            "device": "Dispositivo",
            "voice": "Voz",
            "manual": "Manual"
        }
        return source_map.get(self.source, self.source)

    @property
    def is_normal(self) -> Optional[bool]:
        """
        Verifica si los valores de la medición están dentro de rangos normales.
        Returns:
            Optional[bool]: True si es normal, False si es anormal, None si no se puede determinar
        """
        if self.type == "bp" and self.systolic and self.diastolic:
            # Rango normal de presión arterial: 90-120 mmHg sistólica, 60-80 mmHg diastólica
            return (90 <= self.systolic <= 120) and (60 <= self.diastolic <= 80)
        elif self.type == "spo2" and self.spo2:
            # Rango normal de SpO2: 95-100%
            return self.spo2 >= 95
        elif self.type == "temperature" and self.temperature_c:
            # Rango normal de temperatura: 36-37.5°C
            return 36 <= self.temperature_c <= 37.5

        return None

    @property
    def formatted_value(self) -> str:
        """
        Devuelve una representación formateada de los valores de la medición.
        Returns:
            str: Valores formateados para mostrar
        """
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

# =====================================================================
# MODELOS DE TAREAS Y CATEGORÍAS
# =====================================================================

class TaskCategory(Base):
    """
    Modelo de Categoría de Tareas para el sistema de residencias.
    Representa las categorías en las que se organizan las tareas.
    Las categorías son únicas por residencia.
    """
    __tablename__ = "task_category"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la categoría de tarea."""
        return f"<TaskCategory(id={self.id[:8]}..., name={self.name}, residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la categoría de tarea."""
        return f"Categoría: {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la categoría está activa (no eliminada)."""
        return self.deleted_at is None

class TaskTemplate(Base):
    """
    Modelo de Plantilla de Tarea para el sistema de residencias.
    Representa las plantillas de tareas que pueden ser asignadas a residentes.
    """
    __tablename__ = "task_template"

    # ---------- Identificación ----------
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

    # ---------- Estados posibles de la tarea ----------
    status1: Mapped[Optional[str]] = mapped_column(Text)
    status2: Mapped[Optional[str]] = mapped_column(Text)
    status3: Mapped[Optional[str]] = mapped_column(Text)
    status4: Mapped[Optional[str]] = mapped_column(Text)
    status5: Mapped[Optional[str]] = mapped_column(Text)
    status6: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Configuración adicional ----------
    audio_phrase: Mapped[Optional[str]] = mapped_column(Text)
    is_block: Mapped[Optional[bool]] = mapped_column(Boolean)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la plantilla de tarea."""
        return f"<TaskTemplate(id={self.id[:8]}..., name={self.name}, category_id={self.task_category_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la plantilla de tarea."""
        return f"Plantilla: {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la plantilla está activa (no eliminada)."""
        return self.deleted_at is None

    @property
    def available_statuses(self) -> list[str]:
        """
        Devuelve una lista de los estados disponibles para esta tarea.
        Returns:
            list[str]: Lista de estados configurados para la tarea
        """
        statuses = []
        for i in range(1, 7):
            status = getattr(self, f"status{i}", None)
            if status:
                statuses.append(status)
        return statuses

class TaskApplication(Base):
    """
    Modelo de Aplicación de Tarea para el sistema de residencias.
    Representa la asignación de una plantilla de tarea a un residente específico.
    """
    __tablename__ = "task_application"

    # ---------- Identificación ----------
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

    # ---------- Aplicación ----------
    applied_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---------- Estado de la aplicación ----------
    selected_status_index: Mapped[Optional[int]] = mapped_column(SmallInteger)
    selected_status_text: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Auditoría ----------
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la aplicación de tarea."""
        return f"<TaskApplication(id={self.id[:8]}..., resident_id={self.resident_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la aplicación de tarea."""
        return f"Tarea aplicada a residente {self.resident_id[:8]}..."

    @property
    def is_active(self) -> bool:
        """Verifica si la aplicación está activa (no eliminada)."""
        return self.deleted_at is None

    @property
    def current_status(self) -> Optional[str]:
        """
        Devuelve el estado actual de la aplicación.
        Returns:
            Optional[str]: Estado actual o None si no hay estado seleccionado
        """
        return self.selected_status_text

    @property
    def is_completed(self) -> bool:
        """
        Verifica si la tarea está completada.
        Considera completada si tiene un estado seleccionado.
        Returns:
            bool: True si está completada, False en caso contrario
        """
        return self.selected_status_text is not None

# =====================================================================
# MODELO DE ETIQUETAS PARA RESIDENTES
# =====================================================================

class Tag(Base):
    """
    Modelo de Etiqueta para el sistema de residencias.
    Representa etiquetas que pueden ser asignadas a residentes para categorización.
    """
    __tablename__ = "tag"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la etiqueta."""
        return f"<Tag(id={self.id[:8]}..., name={self.name})>"

    def __str__(self) -> str:
        """Representación legible de la etiqueta."""
        return f"Etiqueta: {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la etiqueta está activa (no eliminada)."""
        return self.deleted_at is None

class ResidentTag(Base):
    """
    Modelo de relación entre Residentes y Etiquetas.
    Representa la asignación de etiquetas a residentes específicos.
    """
    __tablename__ = "resident_tag"

    # ---------- Claves primarias compuestas ----------
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

    # ---------- Asignación ----------
    assigned_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        """Representación en string de la relación residente-etiqueta."""
        return f"<ResidentTag(resident_id={self.resident_id[:8]}..., tag_id={self.tag_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la relación residente-etiqueta."""
        return f"Etiqueta {self.tag_id[:8]}... asignada a residente {self.resident_id[:8]}..."

    @property
    def assignment_info(self) -> dict:
        """
        Devuelve un diccionario con la información de la asignación.
        Returns:
            dict: Información completa de la asignación
        """
        return {
            "resident_id": self.resident_id,
            "tag_id": self.tag_id,
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at
        }

# =====================================================================
# MODELO DE REGISTRO DE EVENTOS DEL SISTEMA
# =====================================================================

class EventLog(Base):
    """
    Modelo de Registro de Eventos para el sistema de residencias.
    Registra todas las acciones importantes realizadas en el sistema para auditoría.
    """
    __tablename__ = "event_log"

    # ---------- Identificación ----------
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---------- Actor y contexto ----------
    actor_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    residence_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id"))

    # ---------- Información del evento ----------
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    action: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Timestamps ----------
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---------- Metadatos adicionales ----------
    meta: Mapped[Optional[Dict]] = mapped_column(JSONB)

    def __repr__(self) -> str:
        """Representación en string del evento."""
        return f"<EventLog(id={self.id}, action={self.action}, entity={self.entity})>"

    def __str__(self) -> str:
        """Representación legible del evento."""
        actor_info = f"Usuario {self.actor_user_id[:8]}..." if self.actor_user_id else "Sistema"
        return f"{actor_info} {self.action} {self.entity}"

    @property
    def event_info(self) -> dict:
        """
        Devuelve un diccionario con la información completa del evento.
        Returns:
            dict: Información estructurada del evento
        """
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
        """
        Devuelve una descripción legible de la acción en español.
        Returns:
            str: Descripción de la acción en español
        """
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
        """
        Devuelve una descripción legible de la entidad en español.
        Returns:
            str: Descripción de la entidad en español
        """
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
        """
        Devuelve una descripción formateada del evento.
        Returns:
            str: Descripción completa y legible del evento
        """
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
        """
        Verifica si el evento fue generado por el sistema.
        Returns:
            bool: True si es un evento del sistema, False si fue generado por un usuario
        """
        return self.actor_user_id is None

    @property
    def is_security_related(self) -> bool:
        """
        Verifica si el evento está relacionado con seguridad.
        Returns:
            bool: True si es un evento de seguridad, False en caso contrario
        """
        security_actions = {"login", "logout", "create", "delete", "update"}
        security_entities = {"user", "residence"}
        return self.action in security_actions or self.entity in security_entities

    @property
    def event_age(self) -> Optional[datetime.timedelta]:
        """
        Devuelve el tiempo transcurrido desde que ocurrió el evento.
        Returns:
            Optional[datetime.timedelta]: Tiempo transcurrido o None si el evento no tiene timestamp
        """
        if self.at:
            return datetime.now(self.at.tzinfo) - self.at
        return None

# =====================================================================
# EXPORTACIONES
# =====================================================================

__all__ = [
    # Base y enums
    "Base",
    "user_role_enum",
    "resident_status_enum", 
    "device_type_enum",
    "measurement_type_enum",
    "measurement_source_enum",

    # Modelos principales
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
