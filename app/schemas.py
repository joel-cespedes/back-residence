# app/schemas.py
from __future__ import annotations

from typing import Optional, Literal, List, Dict
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field

# =========================================================
# ENUMS (deben coincidir con la BD)
# =========================================================

UserRole = Literal["superadmin", "manager", "professional"]

ResidentStatus = Literal["active", "discharged", "deceased"]

DeviceType = Literal["blood_pressure", "pulse_oximeter", "scale", "thermometer"]

MeasurementSource = Literal["device", "voice", "manual"]
MeasurementType   = Literal["bp", "spo2", "weight", "temperature"]


# =========================================================
# AUTH
# =========================================================

class LoginRequest(BaseModel):
    alias: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class Me(BaseModel):
    id: str
    role: UserRole


# =========================================================
# RESIDENCES
# =========================================================

class ResidenceCreate(BaseModel):
    name: str
    address: Optional[str] = None
    # phone/email se guardan cifrados en modelo; aquí opcionales si tu endpoint los acepta
    phone: Optional[str] = None
    email: Optional[str] = None


class ResidenceUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class ResidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: Optional[str] = None


# =========================================================
# ESTRUCTURA (Floor / Room / Bed)
# =========================================================

class FloorCreate(BaseModel):
    name: str


class FloorUpdate(BaseModel):
    name: Optional[str] = None


class FloorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    name: str


class RoomCreate(BaseModel):
    floor_id: str
    name: str


class RoomUpdate(BaseModel):
    name: Optional[str] = None


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    floor_id: str
    name: str


class BedCreate(BaseModel):
    room_id: str
    name: str


class BedUpdate(BaseModel):
    name: Optional[str] = None


class BedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    room_id: str
    name: str


# =========================================================
# RESIDENTS
# =========================================================

class ResidentCreate(BaseModel):
    full_name: str
    birth_date: date
    sex: Optional[str] = None
    gender: Optional[str] = None
    comments: Optional[str] = None
    # status en alta: por defecto 'active'
    status: ResidentStatus = "active"
    # asignación opcional de cama (solo si activo)
    bed_id: Optional[str] = None


class ResidentUpdate(BaseModel):
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    sex: Optional[str] = None
    gender: Optional[str] = None
    comments: Optional[str] = None
    status: Optional[ResidentStatus] = None
    bed_id: Optional[str] = None  # permitir cambiar cama desde aquí si tu router lo soporta


class ResidentChangeBed(BaseModel):
    new_bed_id: str
    changed_at: Optional[datetime] = None  # opcional; si no viene, el backend pone now()


class ResidentOut(BaseModel):
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
    created_at: datetime
    updated_at: datetime


# =========================================================
# TAGS
# =========================================================

class TagCreate(BaseModel):
    name: str


class TagUpdate(BaseModel):
    name: Optional[str] = None


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class ResidentTagAssign(BaseModel):
    resident_id: str
    tag_id: str


# =========================================================
# DEVICES
# =========================================================

class DeviceCreate(BaseModel):
    type: DeviceType
    name: str
    mac: str
    battery_percent: Optional[int] = Field(None, ge=0, le=100)


class DeviceUpdate(BaseModel):
    type: Optional[DeviceType] = None
    name: Optional[str] = None
    mac: Optional[str] = None
    battery_percent: Optional[int] = Field(None, ge=0, le=100)


class DeviceOut(BaseModel):
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


# =========================================================
# TASKS (Plantillas y Aplicaciones)
# =========================================================

class TaskCategoryCreate(BaseModel):
    name: str


class TaskCategoryUpdate(BaseModel):
    name: Optional[str] = None


class TaskCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class TaskTemplateCreate(BaseModel):
    task_category_id: str
    name: str
    status1: Optional[str] = None
    status2: Optional[str] = None
    status3: Optional[str] = None
    status4: Optional[str] = None
    status5: Optional[str] = None
    status6: Optional[str] = None
    audio_phrase: Optional[str] = None
    is_block: Optional[bool] = None


class TaskTemplateUpdate(BaseModel):
    task_category_id: Optional[str] = None
    name: Optional[str] = None
    status1: Optional[str] = None
    status2: Optional[str] = None
    status3: Optional[str] = None
    status4: Optional[str] = None
    status5: Optional[str] = None
    status6: Optional[str] = None
    audio_phrase: Optional[str] = None
    is_block: Optional[bool] = None


class TaskTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    task_category_id: str
    name: str
    status1: Optional[str] = None
    status2: Optional[str] = None
    status3: Optional[str] = None
    status4: Optional[str] = None
    status5: Optional[str] = None
    status6: Optional[str] = None
    audio_phrase: Optional[str] = None
    is_block: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class TaskApplicationCreate(BaseModel):
    resident_id: str
    task_template_id: str
    # el backend rellenará selected_status_text si envías index
    selected_status_index: Optional[int] = Field(None, ge=1, le=6)
    selected_status_text: Optional[str] = None
    applied_at: Optional[datetime] = None  # if None → now()


class TaskApplicationUpdate(BaseModel):
    selected_status_index: Optional[int] = Field(None, ge=1, le=6)
    selected_status_text: Optional[str] = None
    applied_at: Optional[datetime] = None


class TaskApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    resident_id: str
    task_template_id: str
    applied_by: str
    applied_at: datetime
    selected_status_index: Optional[int] = None
    selected_status_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


# =========================================================
# MEASUREMENTS
# =========================================================

class MeasurementCreate(BaseModel):
    """
    Crear medición. El backend valida coherencia según 'type'.
    - bp  : requiere systolic y diastolic; pulse_bpm opcional
    - spo2: requiere spo2; pulse_bpm opcional
    - weight: requiere weight_kg (float, 1 decimal permitido)
    - temperature: requiere temperature_c (int)
    """
    resident_id: str
    source: MeasurementSource
    type: MeasurementType
    taken_at: datetime

    device_id: Optional[str] = None

    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse_bpm: Optional[int] = None
    spo2: Optional[int] = None
    weight_kg: Optional[float] = None
    temperature_c: Optional[int] = None


class MeasurementUpdate(BaseModel):
    """
    Actualizar medición: todos los campos opcionales.
    """
    source: Optional[MeasurementSource] = None
    type: Optional[MeasurementType] = None
    taken_at: Optional[datetime] = None

    device_id: Optional[str] = None

    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse_bpm: Optional[int] = None
    spo2: Optional[int] = None
    weight_kg: Optional[float] = None
    temperature_c: Optional[int] = None


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    residence_id: str
    resident_id: str
    recorded_by: str
    source: MeasurementSource
    device_id: Optional[str] = None
    type: MeasurementType

    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse_bpm: Optional[int] = None
    spo2: Optional[int] = None
    weight_kg: Optional[float] = None
    temperature_c: Optional[int] = None

    taken_at: datetime
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


# =========================================================
# DASHBOARD SCHEMAS
# =========================================================

class DashboardMetric(BaseModel):
    title: str
    value: str
    change: str
    changeType: Literal['positive', 'negative']
    icon: str
    color: str
    colorIcon: Optional[str] = None

class MonthlyData(BaseModel):
    month: str
    value: int

class YearComparison(BaseModel):
    year: int
    data: List[MonthlyData]

class ResidentStats(BaseModel):
    total: int
    active: int
    discharged: int
    deceased: int
    with_bed: int
    without_bed: int

class MeasurementStats(BaseModel):
    total_measurements: int
    by_type: Dict[str, int]
    by_source: Dict[str, int]
    last_30_days: int
    trend: Literal['increasing', 'decreasing', 'stable']

class TaskStats(BaseModel):
    total_applications: int
    completion_rate: float
    by_category: Dict[str, Dict[str, int]]
    last_30_days: int

class DeviceStats(BaseModel):
    total_devices: int
    by_type: Dict[str, int]
    low_battery: int
    average_battery: float

class DashboardData(BaseModel):
    metrics: List[DashboardMetric]
    resident_stats: ResidentStats
    measurement_stats: MeasurementStats
    task_stats: TaskStats
    device_stats: DeviceStats
    yearly_comparison: List[YearComparison]
    recent_activity: List[Dict]


# =========================================================
# PAGINATION SCHEMAS
# =========================================================

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")
    search: Optional[str] = Field(None, description="Search term")
    sort_by: Optional[str] = Field(None, description="Sort field")
    sort_order: Optional[Literal['asc', 'desc']] = Field('asc', description="Sort order")

class PaginatedResponse(BaseModel):
    items: List[Dict]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool

class FilterParams(BaseModel):
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    status: Optional[str] = Field(None, description="Filter by status")
    type: Optional[str] = Field(None, description="Filter by type")
    search: Optional[str] = Field(None, description="Search term")
