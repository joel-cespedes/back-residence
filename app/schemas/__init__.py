# =====================================================================
# MÓDULO DE ESQUEMAS DE PYDANTIC
# =====================================================================

"""
Módulo que contiene todos los esquemas de Pydantic para la API del sistema de residencias.
Cada esquema está separado en su propio archivo por entidad para mantener una organización clara.
"""

# Importar enumeraciones comunes
from .enums import (
    UserRole,
    ResidentStatus,
    DeviceType,
    MeasurementSource,
    MeasurementType
)

# Importar esquemas por entidad
from .auth import LoginRequest, TokenResponse, Me
from .residence import ResidenceCreate, ResidenceUpdate, ResidenceOut
from .location import FloorCreate, FloorUpdate, FloorOut, RoomCreate, RoomUpdate, RoomOut, BedCreate, BedUpdate, BedOut
from .resident import ResidentCreate, ResidentUpdate, ResidentChangeBed, ResidentOut
from .device import DeviceCreate, DeviceUpdate, DeviceOut
from .task import TaskCategoryCreate, TaskCategoryUpdate, TaskCategoryOut, TaskTemplateCreate, TaskTemplateUpdate, TaskTemplateOut, TaskApplicationCreate, TaskApplicationUpdate, TaskApplicationOut
from .measurement import MeasurementCreate, MeasurementUpdate, MeasurementOut
from .tag import TagCreate, TagUpdate, TagOut, ResidentTagAssign
from .dashboard import DashboardMetric, MonthlyData, YearComparison, ResidentStats, MeasurementStats, TaskStats, TaskCategoryWithCount, MonthlyResidentData, NewResidentStats, DeviceStats, DashboardData
from .pagination import PaginationParams, PaginatedResponse, FilterParams

# Exportar todos los esquemas para fácil importación
__all__ = [
    # Enumeraciones comunes
    "UserRole",
    "ResidentStatus",
    "DeviceType",
    "MeasurementSource",
    "MeasurementType",

    # Autenticación
    "LoginRequest",
    "TokenResponse",
    "Me",

    # Residencias
    "ResidenceCreate",
    "ResidenceUpdate",
    "ResidenceOut",

    # Estructura (Piso/Habitación/Cama)
    "FloorCreate",
    "FloorUpdate",
    "FloorOut",
    "RoomCreate",
    "RoomUpdate",
    "RoomOut",
    "BedCreate",
    "BedUpdate",
    "BedOut",

    # Residentes
    "ResidentCreate",
    "ResidentUpdate",
    "ResidentChangeBed",
    "ResidentOut",

    # Dispositivos
    "DeviceCreate",
    "DeviceUpdate",
    "DeviceOut",

    # Tareas
    "TaskCategoryCreate",
    "TaskCategoryUpdate",
    "TaskCategoryOut",
    "TaskTemplateCreate",
    "TaskTemplateUpdate",
    "TaskTemplateOut",
    "TaskApplicationCreate",
    "TaskApplicationUpdate",
    "TaskApplicationOut",

    # Mediciones
    "MeasurementCreate",
    "MeasurementUpdate",
    "MeasurementOut",

    # Etiquetas
    "TagCreate",
    "TagUpdate",
    "TagOut",
    "ResidentTagAssign",

    # Dashboard
    "DashboardMetric",
    "MonthlyData",
    "YearComparison",
    "ResidentStats",
    "MeasurementStats",
    "TaskStats",
    "TaskCategoryWithCount",
    "MonthlyResidentData",
    "NewResidentStats",
    "DeviceStats",
    "DashboardData",

    # Paginación y Filtros
    "PaginationParams",
    "PaginatedResponse",
    "FilterParams"
]