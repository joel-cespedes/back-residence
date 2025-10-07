# =====================================================================
# ESQUEMAS DE CRONOLOGÍA DE RESIDENTE
# =====================================================================

from __future__ import annotations

from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict


# =========================================================
# EVENTOS DE CRONOLOGÍA
# =========================================================

class ChronologyEventBase(BaseModel):
    """Base para todos los eventos de cronología"""
    event_type: str  # "measurement" | "task" | "bed_change" | "status_change"
    timestamp: datetime
    recorded_by: Optional[str] = None  # ID del usuario
    recorded_by_name: Optional[str] = None  # Nombre del usuario


class MeasurementEvent(ChronologyEventBase):
    """Evento de medición médica"""
    event_type: Literal["measurement"] = "measurement"
    measurement_id: str
    measurement_type: str  # bp, spo2, weight, temperature
    source: str  # device, voice, manual
    device_name: Optional[str] = None
    values: dict  # {systolic: 120, diastolic: 80, ...}


class TaskEvent(ChronologyEventBase):
    """Evento de tarea asignada/completada"""
    event_type: Literal["task"] = "task"
    task_application_id: str
    task_name: str
    task_category: str
    status: Optional[str] = None  # El estado actual de la tarea
    assigned_by: Optional[str] = None
    assigned_by_name: Optional[str] = None


class BedChangeEvent(ChronologyEventBase):
    """Evento de cambio de cama"""
    event_type: Literal["bed_change"] = "bed_change"
    history_id: int
    change_type: str  # bed_assignment, bed_removal, residence_transfer
    previous_location: Optional[str] = None  # "Habitación 101, Cama A"
    new_location: Optional[str] = None  # "Habitación 205, Cama B"
    previous_bed_id: Optional[str] = None
    new_bed_id: Optional[str] = None
    previous_room_id: Optional[str] = None
    new_room_id: Optional[str] = None


class StatusChangeEvent(ChronologyEventBase):
    """Evento de cambio de estado del residente"""
    event_type: Literal["status_change"] = "status_change"
    history_id: int
    previous_status: Optional[str] = None
    new_status: str


# Union type para cualquier evento
ChronologyEvent = MeasurementEvent | TaskEvent | BedChangeEvent | StatusChangeEvent


class ResidentChronologyResponse(BaseModel):
    """Respuesta completa de la cronología de un residente"""
    model_config = ConfigDict(from_attributes=True)

    resident_id: str
    resident_name: str
    events: List[ChronologyEvent]
    total_events: int

    # Estadísticas rápidas
    total_measurements: int
    total_tasks: int
    total_bed_changes: int
    total_status_changes: int


class ChronologyFilters(BaseModel):
    """Filtros para la cronología"""
    include_measurements: bool = True
    include_tasks: bool = True
    include_bed_changes: bool = True
    include_status_changes: bool = True
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 100  # Límite de eventos a retornar
