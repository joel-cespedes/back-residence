# =====================================================================
# MODELO BASE Y ENUMERACIONES PARA LA BASE DE DATOS
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID, BYTEA, ENUM, JSONB
from sqlalchemy import Text, Integer, SmallInteger, Boolean, ForeignKey, Date, DateTime, func
from datetime import datetime, date
from typing import Optional

# ---------- Clase Base para todos los modelos ----------
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