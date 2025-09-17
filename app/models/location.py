# =====================================================================
# MODELOS DE UBICACIÓN (PISOS, HABITACIONES, CAMAS)
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Text, ForeignKey, DateTime, func
from datetime import datetime
from typing import Optional

from .base import Base


class Floor(Base):
    """
    Modelo de Piso para la estructura jerárquica de residencias.
    Representa un piso dentro de una residencia.
    """
    __tablename__ = "floor"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string del piso."""
        return f"<Floor(id={self.id[:8]}..., name={self.name}, residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible del piso."""
        return f"Piso {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si el piso está activo (no eliminado)."""
        return self.deleted_at is None


class Room(Base):
    """
    Modelo de Habitación para la estructura jerárquica de residencias.
    Representa una habitación dentro de un piso.
    """
    __tablename__ = "room"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    floor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("floor.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la habitación."""
        return f"<Room(id={self.id[:8]}..., name={self.name}, floor_id={self.floor_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la habitación."""
        return f"Habitación {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la habitación está activa (no eliminada)."""
        return self.deleted_at is None


class Bed(Base):
    """
    Modelo de Cama para la estructura jerárquica de residencias.
    Representa una cama dentro de una habitación donde se alojan los residentes.
    """
    __tablename__ = "bed"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    room_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("room.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la cama."""
        return f"<Bed(id={self.id[:8]}..., name={self.name}, room_id={self.room_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la cama."""
        return f"Cama {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la cama está activa (no eliminada)."""
        return self.deleted_at is None

    @property
    def is_occupied(self) -> bool:
        """
        Verifica si la cama está ocupada por un residente.
        Esta propiedad requiere una consulta a la base de datos para verificar
        si hay un residente asignado actualmente.
        """
        # Esta propiedad se implementaría con una consulta a la base de datos
        # Por ahora, devuelve False como valor por defecto
        return False