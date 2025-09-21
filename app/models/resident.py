# =====================================================================
# MODELO DE RESIDENTES
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Text, ForeignKey, Date, DateTime, func
from datetime import datetime, date
from typing import Optional

from .base import Base, resident_status_enum

class Resident(Base):
    """
    Modelo de Residente para el sistema de gestión de residencias.
    Representa a las personas que viven en las residencias y reciben cuidados.
    """
    __tablename__ = "resident"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )

    # ---------- Datos personales ----------
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[Optional[str]] = mapped_column(Text)
    comments: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Estado y asignación ----------
    status: Mapped[str] = mapped_column(
        resident_status_enum,
        server_default='active',
        nullable=False
    )
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bed_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("bed.id", ondelete="SET NULL")
    )

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---------- Soft delete ----------
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string del residente."""
        return f"<Resident(id={self.id[:8]}..., name={self.full_name}, status={self.status})>"

    def __str__(self) -> str:
        """Representación legible del residente."""
        return f"Residente {self.full_name} ({self.status})"

    @property
    def age(self) -> Optional[int]:
        """
        Calcula la edad del residente basado en su fecha de nacimiento.
        Returns:
            int: Edad del residente o None si no tiene fecha de nacimiento
        """
        if not self.birth_date:
            return None

        today = date.today()
        age = today.year - self.birth_date.year

        # Ajustar si el cumpleaños aún no ha pasado este año
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age -= 1

        return age

    @property
    def is_active(self) -> bool:
        """
        Verifica si el residente está activo.
        Un residente está activo si su estado es 'active' y no ha sido eliminado.
        """
        return self.status == 'active' and self.deleted_at is None

    @property
    def is_discharged(self) -> bool:
        """Verifica si el residente ha sido dado de alta."""
        return self.status == 'discharged'

    @property
    def is_deceased(self) -> bool:
        """Verifica si el residente ha fallecido."""
        return self.status == 'deceased'

    @property
    def is_assigned_to_bed(self) -> bool:
        """
        Verifica si el residente tiene una cama asignada.
        """
        return self.bed_id is not None

    @property
    def personal_info(self) -> dict:
        """
        Devuelve un diccionario con la información personal del residente.
        """
        return {
            "full_name": self.full_name,
            "birth_date": self.birth_date,
            "age": self.age,
            "sex": self.sex,
            "gender": self.gender,
            "comments": self.comments
        }

    @property
    def location_info(self) -> dict:
        """
        Devuelve un diccionario con la información de ubicación del residente.
        """
        return {
            "residence_id": self.residence_id,
            "bed_id": self.bed_id,
            "is_assigned": self.is_assigned_to_bed
        }