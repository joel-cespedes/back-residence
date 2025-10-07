# =====================================================================
# ESQUEMAS DE MEDICIONES MÉDICAS
# =====================================================================

from __future__ import annotations

from typing import Optional, List
from datetime import datetime, date
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
        recorded_by_name (Optional[str]): Nombre del profesional/gestor que registró la medición
        source (MeasurementSource): Fuente de la medición
        device_id (Optional[str]): ID del dispositivo utilizado
        device_name (Optional[str]): Nombre del dispositivo utilizado
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
    recorded_by_name: Optional[str] = None  # Nombre del profesional/gestor
    source: MeasurementSource
    device_id: Optional[str] = None
    device_name: Optional[str] = None  # Nombre del dispositivo
    type: MeasurementType
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse_bpm: Optional[int] = None
    spo2: Optional[int] = None
    weight_kg: Optional[float] = None
    temperature_c: Optional[float] = None
    taken_at: datetime
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class MeasurementDailySummary(BaseModel):
    """
    Esquema para el resumen diario de mediciones por residente.

    Attributes:
        resident_id (str): ID del residente
        resident_full_name (str): Nombre completo del residente
        bed_name (Optional[str]): Nombre de la cama asignada
        date (date): Fecha de las mediciones
        measurement_count (int): Número total de mediciones del día
        measurement_types (List[str]): Tipos de mediciones realizadas
        first_measurement_time (str): Hora de la primera medición (HH:MM:SS)
        last_measurement_time (str): Hora de la última medición (HH:MM:SS)
    """
    model_config = ConfigDict(from_attributes=True)

    resident_id: str
    resident_full_name: str
    bed_name: Optional[str] = None
    date: date
    measurement_count: int
    measurement_types: List[str]
    first_measurement_time: str
    last_measurement_time: str


# =========================================================
# ESQUEMAS DE VOZ PARA MEDICIONES
# =========================================================

class VoiceMeasurementTranscript(BaseModel):
    """Esquema para el request de procesamiento de voz de mediciones"""
    residence_id: str
    transcript: str


class ResidentOption(BaseModel):
    """Opción de residente para selección cuando hay ambigüedad"""
    id: str
    full_name: str
    room_name: Optional[str] = None
    bed_number: Optional[str] = None
    floor_name: Optional[str] = None


class MeasurementTypeOption(BaseModel):
    """Opción de tipo de medición"""
    type: str
    label: str


class MeasurementValuesOut(BaseModel):
    """Valores de una medición según el tipo"""
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse_bpm: Optional[int] = None
    spo2: Optional[int] = None
    weight_kg: Optional[float] = None
    temperature_c: Optional[float] = None


class VoiceMeasurementData(BaseModel):
    """Datos de la medición procesada exitosamente"""
    id: str
    resident_id: str
    resident_name: str
    measurement_type: str  # bp, spo2, weight, temperature
    values: MeasurementValuesOut
    source: str  # "voice"
    recorded_at: datetime
    recorded_by: str


class VoiceMeasurementResponse(BaseModel):
    """
    Respuesta del procesamiento de voz de mediciones

    Casos:
    1. status=success: Match único, medición registrada
    2. status=ambiguous: Residente ambiguo (resident_options)
    3. status=error: Error en el procesamiento
    """
    status: str  # "success", "ambiguous", "error"
    message: str

    # Caso success
    measurement: Optional[VoiceMeasurementData] = None
    confirmation_message: Optional[str] = None

    # Caso ambiguous - residente
    resident_options: Optional[List[ResidentOption]] = None
    parsed_measurement: Optional[dict] = None

    # Caso error
    error_code: Optional[str] = None
    details: Optional[dict] = None


class VoiceMeasurementConfirm(BaseModel):
    """Esquema para confirmar una medición después de resolver ambigüedad"""
    residence_id: str
    resident_id: str
    measurement_type: str  # bp, spo2, weight, temperature
    values: dict
    transcript: Optional[str] = None