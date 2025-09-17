# =====================================================================
# ESQUEMAS DE PAGINACIÓN Y FILTROS
# =====================================================================

from __future__ import annotations

from typing import Optional, List, Dict, Literal
from datetime import datetime
from pydantic import BaseModel, Field

# =========================================================
# ESQUEMAS DE PAGINACIÓN
# =========================================================

class PaginationParams(BaseModel):
    """
    Esquema para parámetros de paginación.

    Attributes:
        page (int): Número de página (default: 1, mínimo: 1)
        size (int): Tamaño de página (default: 20, rango: 1-100)
        search (Optional[str]): Término de búsqueda
        sort_by (Optional[str]): Campo de ordenamiento
        sort_order (Optional[Literal['asc', 'desc']]): Orden de clasificación
    """
    page: int = Field(1, ge=1, description="Número de página")
    size: int = Field(20, ge=1, le=100, description="Tamaño de página")
    search: Optional[str] = Field(None, description="Término de búsqueda")
    sort_by: Optional[str] = Field(None, description="Campo de ordenamiento")
    sort_order: Optional[Literal['asc', 'desc']] = Field('asc', description="Orden de clasificación")


class PaginatedResponse(BaseModel):
    """
    Esquema para respuesta paginada.

    Attributes:
        items (List[Dict]): Elementos de la página actual
        total (int): Total de elementos
        page (int): Página actual
        size (int): Tamaño de página
        pages (int): Total de páginas
        has_next (bool): Indica si hay página siguiente
        has_prev (bool): Indica si hay página anterior
    """
    items: List[Dict]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


# =========================================================
# ESQUEMAS DE FILTROS
# =========================================================

class FilterParams(BaseModel):
    """
    Esquema para parámetros de filtrado.

    Attributes:
        date_from (Optional[datetime]): Filtrar desde fecha
        date_to (Optional[datetime]): Filtrar hasta fecha
        status (Optional[str]): Filtrar por estado
        type (Optional[str]): Filtrar por tipo
        search (Optional[str]): Término de búsqueda
    """
    date_from: Optional[datetime] = Field(None, description="Filtrar desde fecha")
    date_to: Optional[datetime] = Field(None, description="Filtrar hasta fecha")
    status: Optional[str] = Field(None, description="Filtrar por estado")
    type: Optional[str] = Field(None, description="Filtrar por tipo")
    search: Optional[str] = Field(None, description="Término de búsqueda")