# =====================================================================
# MODELO DE DISPOSITIVOS MÉDICOS
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Text, SmallInteger, ForeignKey, DateTime, func
from datetime import datetime
from typing import Optional

from .base import Base, device_type_enum

class Device(Base):
    """
    Modelo de Dispositivo médico para el sistema de residencias.
    Representa los dispositivos médicos utilizados para tomar mediciones de los residentes.
    """
    __tablename__ = "device"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )

    # ---------- Información del dispositivo ----------
    type: Mapped[str] = mapped_column(device_type_enum, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mac: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # ---------- Estado del dispositivo ----------
    battery_percent: Mapped[Optional[int]] = mapped_column(SmallInteger)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string del dispositivo."""
        return f"<Device(id={self.id[:8]}..., name={self.name}, type={self.type}, mac={self.mac})>"

    def __str__(self) -> str:
        """Representación legible del dispositivo."""
        return f"Dispositivo {self.name} ({self.type})"

    @property
    def is_active(self) -> bool:
        """
        Verifica si el dispositivo está activo.
        Un dispositivo está activo si no ha sido eliminado (soft delete).
        """
        return self.deleted_at is None

    @property
    def battery_status(self) -> str:
        """
        Devuelve una descripción del estado de la batería.
        Returns:
            str: Descripción del nivel de batería
        """
        if self.battery_percent is None:
            return "Desconocido"

        if self.battery_percent >= 80:
            return "Excelente"
        elif self.battery_percent >= 50:
            return "Bueno"
        elif self.battery_percent >= 20:
            return "Bajo"
        else:
            return "Crítico"

    @property
    def is_low_battery(self) -> bool:
        """
        Verifica si la batería está baja (menos de 20%).
        Returns:
            bool: True si la batería está baja, False en caso contrario
        """
        return self.battery_percent is not None and self.battery_percent < 20

    @property
    def needs_maintenance(self) -> bool:
        """
        Verifica si el dispositivo necesita mantenimiento.
        Considera que necesita mantenimiento si la batería está baja.
        Returns:
            bool: True si necesita mantenimiento, False en caso contrario
        """
        return self.is_low_battery

    @property
    def device_info(self) -> dict:
        """
        Devuelve un diccionario con la información completa del dispositivo.
        Returns:
            dict: Información del dispositivo incluyendo estado de batería
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "mac": self.mac,
            "battery_percent": self.battery_percent,
            "battery_status": self.battery_status,
            "is_low_battery": self.is_low_battery,
            "needs_maintenance": self.needs_maintenance,
            "residence_id": self.residence_id,
            "is_active": self.is_active
        }

    @property
    def human_readable_type(self) -> str:
        """
        Devuelve una descripción legible del tipo de dispositivo.
        Returns:
            str: Descripción del tipo de dispositivo en español
        """
        type_map = {
            "blood_pressure": "Tensiómetro",
            "pulse_oximeter": "Pulsioxímetro",
            "scale": "Báscula",
            "thermometer": "Termómetro"
        }
        return type_map.get(self.type, self.type)