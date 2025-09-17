# =====================================================================
# ESQUEMAS DE RESIDENCIAS
# =====================================================================

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict

# =========================================================
# ESQUEMAS DE RESIDENCIAS
# =========================================================

class ResidenceCreate(BaseModel):
    """
    Esquema para la creación de una nueva residencia.

    Attributes:
        name (str): Nombre de la residencia (obligatorio)
        address (Optional[str]): Dirección física de la residencia
        phone (Optional[str]): Teléfono de contacto (se guardará cifrado)
        email (Optional[str]): Email de contacto (se guardará cifrado)
    """
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class ResidenceUpdate(BaseModel):
    """
    Esquema para la actualización de una residencia existente.

    Attributes:
        name (Optional[str]): Nuevo nombre de la residencia
        address (Optional[str]): Nueva dirección de la residencia
        phone (Optional[str]): Nuevo teléfono de contacto
        email (Optional[str]): Nuevo email de contacto
    """
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class ResidenceOut(BaseModel):
    """
    Esquema para la salida de datos de residencia.

    Attributes:
        id (str): Identificador único de la residencia
        name (str): Nombre de la residencia
        address (Optional[str]): Dirección de la residencia
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: Optional[str] = None