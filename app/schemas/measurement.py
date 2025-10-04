# =====================================================================
# ESQUEMAS DE MEDICIONES MÉDICAS
# =====================================================================

from __future__ import annotations

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from .enums import MeasurementSource, MeasurementType

# =========================================================
# ESQUEMAS DE MEDICIONES
# =========================================================

class MeasurementCreate(BaseModel):
    """
    Esquema para la creación de una nueva medición médica.

    El backend valida la coherencia según el 'type':
    - bp: requiere systolic y diastolic; pulse_bpm opcional
    - spo2: requiere spo2; pulse_bpm opcional
    - weight: requiere weight_kg (float, 1 decimal permitido)
    - temperature: requiere temperature_c (int)

    Attributes:
        resident_id (str): ID del residente al que se le toma la medición
        source (MeasurementSource): Fuente de la medición
        type (MeasurementType): Tipo de medición
        taken_at (datetime): Fecha y hora en que se tomó la medición
        device_id (Optional[str]): ID del dispositivo utilizado
        systolic (Optional[int]): Presión sistólica (para bp)
        diastolic (Optional[int]): Presión diastólica (para bp)
        pulse_bpm (Optional[int]): Pulso en BPM (para bp y spo2)
        spo2 (Optional[int]): Saturación de oxígeno (para spo2)
        weight_kg (Optional[float]): Peso en kg (para weight)
        temperature_c (Optional[int]): Temperatura en °C (para temperature)
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
    Esquema para la actualización de una medición existente.
    Todos los campos son opcionales para permitir actualizaciones parciales.

    Attributes:
        source (Optional[MeasurementSource]): Nueva fuente de la medición
        type (Optional[MeasurementType]): Nuevo tipo de medición
        taken_at (Optional[datetime]): Nueva fecha y hora
        device_id (Optional[str]): Nuevo dispositivo utilizado
        systolic (Optional[int]): Nueva presión sistólica
        diastolic (Optional[int]): Nueva presión diastólica
        pulse_bpm (Optional[int]): Nuevo pulso en BPM
        spo2 (Optional[int]): Nueva saturación de oxígeno
        weight_kg (Optional[float]): Nuevo peso en kg
        temperature_c (Optional[int]): Nueva temperatura en °C
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
    """
    Esquema para la salida de datos de medición.

    Attributes:
        id (str): Identificador único de la medición
        residence_id (str): ID de la residencia a la que pertenece
        resident_id (str): ID del residente medido
        resident_full_name (Optional[str]): Nombre completo del residente
        bed_name (Optional[str]): Nombre de la cama asignada al residente
        recorded_by (str): ID del usuario que registró la medición
        source (MeasurementSource): Fuente de la medición
        device_id (Optional[str]): ID del dispositivo utilizado
        type (MeasurementType): Tipo de medición
        systolic (Optional[int]): Presión sistólica
        diastolic (Optional[int]): Presión diastólica
        pulse_bpm (Optional[int]): Pulso en BPM
        spo2 (Optional[int]): Saturación de oxígeno
        weight_kg (Optional[float]): Peso en kg
        temperature_c (Optional[int]): Temperatura en °C
        taken_at (datetime): Fecha y hora de la medición
        created_at (datetime): Fecha de creación del registro
        updated_at (datetime): Fecha de última actualización
        deleted_at (Optional[datetime]): Fecha de eliminación (soft delete)
    """
    model_config = ConfigDict(from_attributes=True, extra='allow')

    id: str
    residence_id: str
    resident_id: str
    resident_full_name: Optional[str] = None
    bed_name: Optional[str] = None
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