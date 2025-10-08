# =====================================================================
# ESQUEMAS DE ESTRUCTURA FÍSICA (Piso / Habitación / Cama)
# =====================================================================

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict

# =========================================================
# ESQUEMAS DE PISOS
# =========================================================

class FloorCreate(BaseModel):
    """
    Esquema para la creación de un nuevo piso.

    Attributes:
        name (str): Nombre del piso (obligatorio)
    """
    name: str


class FloorUpdate(BaseModel):
    """
    Esquema para la actualización de un piso existente.

    Attributes:
        name (Optional[str]): Nuevo nombre del piso
        residence_id (Optional[str]): Nueva residencia asignada
    """
    name: Optional[str] = None
    residence_id: Optional[str] = None


class FloorOut(BaseModel):
    """
    Esquema para la salida de datos de piso.

    Attributes:
        id (str): Identificador único del piso
        residence_id (str): ID de la residencia a la que pertenece
        name (str): Nombre del piso
        residence_name (Optional[str]): Nombre de la residencia
        created_at (Optional[str]): Fecha de creación
        updated_at (Optional[str]): Fecha de actualización
    """
    model_config = ConfigDict(from_attributes=True, extra='allow')

    id: str
    residence_id: str
    name: str
    residence_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# =========================================================
# ESQUEMAS DE HABITACIONES
# =========================================================

class RoomCreate(BaseModel):
    """
    Esquema para la creación de una nueva habitación.

    Attributes:
        floor_id (str): ID del piso al que pertenece la habitación
        name (str): Nombre de la habitación
    """
    floor_id: str
    name: str


class RoomUpdate(BaseModel):
    """
    Esquema para la actualización de una habitación existente.

    Attributes:
        name (Optional[str]): Nuevo nombre de la habitación
        floor_id (Optional[str]): Nuevo piso de la habitación
    """
    name: Optional[str] = None
    floor_id: Optional[str] = None


class RoomOut(BaseModel):
    """
    Esquema para la salida de datos de habitación.

    Attributes:
        id (str): Identificador único de la habitación
        residence_id (str): ID de la residencia a la que pertenece
        floor_id (str): ID del piso al que pertenece
        name (str): Nombre de la habitación
        floor_name (Optional[str]): Nombre del piso
        residence_name (Optional[str]): Nombre de la residencia
        created_at (Optional[str]): Fecha de creación
        updated_at (Optional[str]): Fecha de actualización
    """
    model_config = ConfigDict(from_attributes=True, extra='allow')

    id: str
    residence_id: str
    floor_id: str
    name: str
    floor_name: Optional[str] = None
    residence_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# =========================================================
# ESQUEMAS DE CAMAS
# =========================================================

class BedCreate(BaseModel):
    """
    Esquema para la creación de una nueva cama.

    Attributes:
        room_id (str): ID de la habitación a la que pertenece la cama
        name (str): Nombre de la cama
    """
    room_id: str
    name: str


class BedUpdate(BaseModel):
    """
    Esquema para la actualización de una cama existente.

    Attributes:
        name (Optional[str]): Nuevo nombre de la cama
        residence_id (Optional[str]): Nueva residencia a la que pertenece la cama
        floor_id (Optional[str]): Nuevo piso al que pertenece la cama
        room_id (Optional[str]): Nueva habitación a la que pertenece la cama
    """
    name: Optional[str] = None
    residence_id: Optional[str] = None
    floor_id: Optional[str] = None
    room_id: Optional[str] = None


class BedOut(BaseModel):
    """
    Esquema para la salida de datos de cama.

    Attributes:
        id (str): Identificador único de la cama
        residence_id (str): ID de la residencia a la que pertenece
        room_id (str): ID de la habitación a la que pertenece
        name (str): Nombre de la cama
        room_name (Optional[str]): Nombre de la habitación
        floor_name (Optional[str]): Nombre del piso
        residence_name (Optional[str]): Nombre de la residencia
        resident_name (Optional[str]): Nombre del residente asignado
        created_at (Optional[str]): Fecha de creación
        updated_at (Optional[str]): Fecha de actualización
    """
    model_config = ConfigDict(from_attributes=True, extra='allow')

    id: str
    residence_id: str
    room_id: str
    name: str
    room_name: Optional[str] = None
    floor_name: Optional[str] = None
    residence_name: Optional[str] = None
    resident_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None