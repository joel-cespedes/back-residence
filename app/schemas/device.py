# =====================================================================
# ESQUEMAS DE DISPOSITIVOS
# =====================================================================

from __future__ import annotations

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from .enums import DeviceType

# =========================================================
# ESQUEMAS DE DISPOSITIVOS
# =========================================================

class DeviceCreate(BaseModel):
    """
    Esquema para la creación de un nuevo dispositivo médico.

    Attributes:
        type (DeviceType): Tipo de dispositivo médico
        name (str): Nombre o identificador del dispositivo
        mac (str): Dirección MAC del dispositivo
        battery_percent (Optional[int]): Porcentaje de batería (0-100)
    """
    type: DeviceType
    name: str
    mac: str
    battery_percent: Optional[int] = Field(None, ge=0, le=100)


class DeviceUpdate(BaseModel):
    """
    Esquema para la actualización de un dispositivo existente.

    Attributes:
        type (Optional[DeviceType]): Nuevo tipo de dispositivo
        name (Optional[str]): Nuevo nombre del dispositivo
        mac (Optional[str]): Nueva dirección MAC
        battery_percent (Optional[int]): Nuevo porcentaje de batería (0-100)
    """
    type: Optional[DeviceType] = None
    name: Optional[str] = None
    mac: Optional[str] = None
    battery_percent: Optional[int] = Field(None, ge=0, le=100)


class DeviceOut(BaseModel):
    """
    Esquema para la salida de datos de dispositivo.

    Attributes:
        id (str): Identificador único del dispositivo
        residence_id (str): ID de la residencia a la que pertenece
        type (DeviceType): Tipo de dispositivo
        name (str): Nombre del dispositivo
        mac (str): Dirección MAC del dispositivo
        battery_percent (Optional[int]): Porcentaje actual de batería
        created_at (datetime): Fecha de creación del registro
        updated_at (datetime): Fecha de última actualización
        deleted_at (Optional[datetime]): Fecha de eliminación (soft delete)
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    type: DeviceType
    name: str
    mac: str
    battery_percent: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None