# =====================================================================
# ESQUEMAS DE RESIDENTES
# =====================================================================

from __future__ import annotations

from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field

from .enums import ResidentStatus

# =========================================================
# ESQUEMAS DE RESIDENTES
# =========================================================

class ResidentCreate(BaseModel):
    """
    Esquema para la creación de un nuevo residente.

    Attributes:
        full_name (str): Nombre completo del residente
        birth_date (date): Fecha de nacimiento del residente
        sex (Optional[str]): Sexo del residente
        residence_id (str): ID de la residencia a la que pertenece
        status (ResidentStatus): Estado del residente (default: 'active')
        bed_id (Optional[str]): ID de la cama asignada
        room_id (Optional[str]): ID de la habitación asignada
        floor_id (Optional[str]): ID del piso asignado
        comments (Optional[str]): Comentarios adicionales
    """
    full_name: str
    birth_date: date
    sex: Optional[str] = None
    residence_id: str
    status: ResidentStatus = "active"
    bed_id: Optional[str] = None
    room_id: Optional[str] = None
    floor_id: Optional[str] = None
    comments: Optional[str] = None


class ResidentUpdate(BaseModel):
    """
    Esquema para la actualización de un residente existente.

    Attributes:
        full_name (Optional[str]): Nuevo nombre completo
        birth_date (Optional[date]): Nueva fecha de nacimiento
        sex (Optional[str]): Nuevo sexo
        comments (Optional[str]): Nuevos comentarios
        status (Optional[ResidentStatus]): Nuevo estado
        residence_id (Optional[str]): Nueva residencia
        bed_id (Optional[str]): Nueva cama asignada
        room_id (Optional[str]): Nueva habitación asignada (independiente de cama)
        floor_id (Optional[str]): Nuevo piso asignado (independiente de cama)
    """
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    sex: Optional[str] = None
    comments: Optional[str] = None
    status: Optional[ResidentStatus] = None
    residence_id: Optional[str] = None
    bed_id: Optional[str] = None
    room_id: Optional[str] = None
    floor_id: Optional[str] = None


class ResidentChangeBed(BaseModel):
    """
    Esquema para el cambio de cama de un residente.

    Attributes:
        new_bed_id (str): ID de la nueva cama a asignar
        changed_at (Optional[datetime]): Fecha y hora del cambio (default: ahora)
    """
    new_bed_id: str
    changed_at: Optional[datetime] = None


class ResidentOut(BaseModel):
    """
    Esquema para la salida de datos de residente.

    Attributes:
        id (str): Identificador único del residente
        residence_id (str): ID de la residencia a la que pertenece
        full_name (str): Nombre completo del residente
        birth_date (date): Fecha de nacimiento
        sex (Optional[str]): Sexo biológico
        gender (Optional[str]): Género de identidad
        comments (Optional[str]): Comentarios adicionales
        status (ResidentStatus): Estado actual del residente
        status_changed_at (Optional[datetime]): Fecha del último cambio de estado
        deleted_at (Optional[datetime]): Fecha de eliminación (soft delete)
        bed_id (Optional[str]): ID de la cama asignada
        room_id (Optional[str]): ID de la habitación asignada
        floor_id (Optional[str]): ID del piso asignado
        bed_name (Optional[str]): Nombre de la cama asignada
        room_name (Optional[str]): Nombre de la habitación asignada
        floor_name (Optional[str]): Nombre del piso asignado
        residence_name (Optional[str]): Nombre de la residencia
        created_at (datetime): Fecha de creación del registro
        updated_at (datetime): Fecha de última actualización
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    full_name: str
    birth_date: date
    sex: Optional[str] = None
    gender: Optional[str] = None
    comments: Optional[str] = None
    status: ResidentStatus
    status_changed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    bed_id: Optional[str] = None
    room_id: Optional[str] = None  # ← AÑADIDO
    floor_id: Optional[str] = None  # ← AÑADIDO
    bed_name: Optional[str] = None
    room_name: Optional[str] = None
    floor_name: Optional[str] = None
    residence_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime