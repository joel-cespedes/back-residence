# =====================================================================
# MODELO DE ETIQUETAS PARA RESIDENTES
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Text, ForeignKey, DateTime, func
from datetime import datetime
from typing import Optional

from .base import Base

class Tag(Base):
    """
    Modelo de Etiqueta para el sistema de residencias.
    Representa etiquetas que pueden ser asignadas a residentes para categorización.
    """
    __tablename__ = "tag"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la etiqueta."""
        return f"<Tag(id={self.id[:8]}..., name={self.name})>"

    def __str__(self) -> str:
        """Representación legible de la etiqueta."""
        return f"Etiqueta: {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la etiqueta está activa (no eliminada)."""
        return self.deleted_at is None


class ResidentTag(Base):
    """
    Modelo de relación entre Residentes y Etiquetas.
    Representa la asignación de etiquetas a residentes específicos.
    """
    __tablename__ = "resident_tag"

    # ---------- Claves primarias compuestas ----------
    resident_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("resident.id", ondelete="CASCADE"),
        primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tag.id", ondelete="RESTRICT"),
        primary_key=True
    )

    # ---------- Asignación ----------
    assigned_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        """Representación en string de la relación residente-etiqueta."""
        return f"<ResidentTag(resident_id={self.resident_id[:8]}..., tag_id={self.tag_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la relación residente-etiqueta."""
        return f"Etiqueta {self.tag_id[:8]}... asignada a residente {self.resident_id[:8]}..."

    @property
    def assignment_info(self) -> dict:
        """
        Devuelve un diccionario con la información de la asignación.
        Returns:
            dict: Información completa de la asignación
        """
        return {
            "resident_id": self.resident_id,
            "tag_id": self.tag_id,
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at
        }