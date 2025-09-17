# =====================================================================
# ESQUEMAS DE ETIQUETAS
# =====================================================================

from __future__ import annotations

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

# =========================================================
# ESQUEMAS DE ETIQUETAS
# =========================================================

class TagCreate(BaseModel):
    """
    Esquema para la creación de una nueva etiqueta.

    Attributes:
        name (str): Nombre de la etiqueta (debe ser único)
    """
    name: str


class TagUpdate(BaseModel):
    """
    Esquema para la actualización de una etiqueta existente.

    Attributes:
        name (Optional[str]): Nuevo nombre de la etiqueta
    """
    name: Optional[str] = None


class TagOut(BaseModel):
    """
    Esquema para la salida de datos de etiqueta.

    Attributes:
        id (str): Identificador único de la etiqueta
        name (str): Nombre de la etiqueta
        created_at (datetime): Fecha de creación del registro
        updated_at (datetime): Fecha de última actualización
        deleted_at (Optional[datetime]): Fecha de eliminación (soft delete)
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


# =========================================================
# ESQUEMAS DE ASIGNACIÓN DE ETIQUETAS A RESIDENTES
# =========================================================

class ResidentTagAssign(BaseModel):
    """
    Esquema para la asignación de etiquetas a residentes.

    Attributes:
        resident_id (str): ID del residente al que se asigna la etiqueta
        tag_id (str): ID de la etiqueta que se asigna
    """
    resident_id: str
    tag_id: str