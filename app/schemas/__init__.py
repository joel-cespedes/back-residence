# =====================================================================
# MÓDULO DE ESQUEMAS DE PYDANTIC
# =====================================================================

"""
Módulo que contiene todos los esquemas de Pydantic para la API del sistema de residencias.
Cada esquema está separado en su propio archivo por entidad para mantener una organización clara.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict

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
from .task import TaskCategoryCreate, TaskCategoryUpdate, TaskCategoryOut, TaskTemplateCreate, TaskTemplateUpdate, TaskTemplateOut, TaskApplicationCreate, TaskApplicationUpdate, TaskApplicationOut, TaskApplicationBatchRequest, TaskApplicationBatchResponse, TaskApplicationDailySummary, TaskApplicationDetail, TaskApplicationResidentDay, UserAssigner, VoiceParseRequest, VoiceParseResponse, VoiceApplicationRequest, VoiceApplicationResponse, ResidentOption, TaskOption, StatusOption
from .measurement import (
    MeasurementCreate, MeasurementUpdate, MeasurementOut, MeasurementDailySummary,
    VoiceMeasurementTranscript, VoiceMeasurementResponse, VoiceMeasurementConfirm,
    VoiceMeasurementData, MeasurementValuesOut, MeasurementTypeOption
)
from .tag import TagCreate, TagUpdate, TagOut, ResidentTagAssign
from .dashboard import DashboardMetric, MonthlyData, YearComparison, ResidentStats, MeasurementStats, TaskStats, TaskCategoryWithCount, MonthlyResidentData, NewResidentStats, DeviceStats, DashboardData
from .pagination import PaginationParams, PaginatedResponse, FilterParams
from .chronology import (
    ChronologyEvent, MeasurementEvent, TaskEvent, BedChangeEvent, StatusChangeEvent,
    ResidentChronologyResponse, ChronologyFilters
)


class UserResidenceAssignment(BaseModel):
    """Residencia asignada a un usuario."""

    id: str


class UserOut(BaseModel):
    """Respuesta estándar para operaciones de usuarios."""

    model_config = ConfigDict(from_attributes=True, extra='allow')

    id: str
    alias: str
    role: UserRole
    residences: List[UserResidenceAssignment]
    created_at: datetime

    # Propiedades adicionales para sistema administrativo
    name: Optional[str] = None
    residence_names: Optional[List[str]] = None
    created_by: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None


class UserCreate(BaseModel):
    """Payload para crear usuarios."""

    alias: str = Field(..., min_length=1, description="Alias único del usuario")
    name: str = Field(..., min_length=1, description="Nombre completo del usuario")
    password: str = Field(..., min_length=6, description="Contraseña definida por el creador")
    role: UserRole = Field(..., description="Rol del nuevo usuario")
    residence_ids: List[str] = Field(default_factory=list, description="Residencias asignadas")

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
    "TaskApplicationBatchRequest",
    "TaskApplicationBatchResponse",
    "TaskApplicationDailySummary",
    "TaskApplicationDetail",
    "TaskApplicationResidentDay",
    "UserAssigner",
    "VoiceParseRequest",
    "VoiceParseResponse",
    "VoiceApplicationRequest",
    "VoiceApplicationResponse",
    "ResidentOption",
    "TaskOption",
    "StatusOption",

    # Mediciones
    "MeasurementCreate",
    "MeasurementUpdate",
    "MeasurementOut",
    "MeasurementDailySummary",
    "VoiceMeasurementTranscript",
    "VoiceMeasurementResponse",
    "VoiceMeasurementConfirm",
    "VoiceMeasurementData",
    "MeasurementValuesOut",
    "MeasurementTypeOption",

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
    "FilterParams",

    # Cronología
    "ChronologyEvent",
    "MeasurementEvent",
    "TaskEvent",
    "BedChangeEvent",
    "StatusChangeEvent",
    "ResidentChronologyResponse",
    "ChronologyFilters",

    # Usuarios
    "UserCreate",
    "UserOut",
    "UserResidenceAssignment",
]
