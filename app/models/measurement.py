# =====================================================================
# MODELO DE MEDICIONES MÉDICAS
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Text, Integer, ForeignKey, DateTime, func
from datetime import datetime
from typing import Optional

from .base import Base, measurement_type_enum, measurement_source_enum

class Measurement(Base):
    """
    Modelo de Medición para el sistema de residencias.
    Representa las mediciones médicas tomadas a los residentes.
    """
    __tablename__ = "measurement"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    resident_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("resident.id", ondelete="RESTRICT"),
        nullable=False
    )

    # ---------- Información de la medición ----------
    recorded_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False
    )
    source: Mapped[str] = mapped_column(measurement_source_enum, nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("device.id")
    )
    type: Mapped[str] = mapped_column(measurement_type_enum, nullable=False)

    # ---------- Valores de medición ----------
    # Presión arterial
    systolic: Mapped[Optional[int]]
    diastolic: Mapped[Optional[int]]

    # Signos vitales
    pulse_bpm: Mapped[Optional[int]]
    spo2: Mapped[Optional[int]]

    # Otros
    weight_kg: Mapped[Optional[float]]
    temperature_c: Mapped[Optional[int]]

    # ---------- Timestamps ----------
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---------- Soft delete ----------
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la medición."""
        return f"<Measurement(id={self.id[:8]}..., type={self.type}, resident_id={self.resident_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la medición."""
        return f"Medición de {self.type} para residente {self.resident_id[:8]}..."

    @property
    def is_active(self) -> bool:
        """Verifica si la medición está activa (no eliminada)."""
        return self.deleted_at is None

    @property
    def measurement_values(self) -> dict:
        """
        Devuelve un diccionario con los valores de la medición según el tipo.
        Returns:
            dict: Valores relevantes según el tipo de medición
        """
        values = {
            "type": self.type,
            "source": self.source,
            "taken_at": self.taken_at,
            "device_id": self.device_id
        }

        if self.type == "bp":
            values.update({
                "systolic": self.systolic,
                "diastolic": self.diastolic,
                "pulse": self.pulse_bpm
            })
        elif self.type == "spo2":
            values.update({
                "spo2": self.spo2,
                "pulse": self.pulse_bpm
            })
        elif self.type == "weight":
            values.update({
                "weight_kg": self.weight_kg
            })
        elif self.type == "temperature":
            values.update({
                "temperature_c": self.temperature_c
            })

        return values

    @property
    def human_readable_type(self) -> str:
        """
        Devuelve una descripción legible del tipo de medición.
        Returns:
            str: Descripción del tipo de medición en español
        """
        type_map = {
            "bp": "Presión arterial",
            "spo2": "Saturación de oxígeno",
            "weight": "Peso",
            "temperature": "Temperatura"
        }
        return type_map.get(self.type, self.type)

    @property
    def human_readable_source(self) -> str:
        """
        Devuelve una descripción legible de la fuente de la medición.
        Returns:
            str: Descripción de la fuente en español
        """
        source_map = {
            "device": "Dispositivo",
            "voice": "Voz",
            "manual": "Manual"
        }
        return source_map.get(self.source, self.source)

    @property
    def is_normal(self) -> Optional[bool]:
        """
        Verifica si los valores de la medición están dentro de rangos normales.
        Returns:
            Optional[bool]: True si es normal, False si es anormal, None si no se puede determinar
        """
        if self.type == "bp" and self.systolic and self.diastolic:
            # Rango normal de presión arterial: 90-120 mmHg sistólica, 60-80 mmHg diastólica
            return (90 <= self.systolic <= 120) and (60 <= self.diastolic <= 80)
        elif self.type == "spo2" and self.spo2:
            # Rango normal de SpO2: 95-100%
            return self.spo2 >= 95
        elif self.type == "temperature" and self.temperature_c:
            # Rango normal de temperatura: 36-37.5°C
            return 36 <= self.temperature_c <= 37.5

        return None

    @property
    def formatted_value(self) -> str:
        """
        Devuelve una representación formateada de los valores de la medición.
        Returns:
            str: Valores formateados para mostrar
        """
        if self.type == "bp" and self.systolic and self.diastolic:
            return f"{self.systolic}/{self.diastolic} mmHg"
        elif self.type == "spo2" and self.spo2:
            return f"{self.spo2}%"
        elif self.type == "weight" and self.weight_kg:
            return f"{self.weight_kg} kg"
        elif self.type == "temperature" and self.temperature_c:
            return f"{self.temperature_c}°C"
        else:
            return "N/A"