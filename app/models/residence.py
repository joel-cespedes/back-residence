# =====================================================================
# MODELO DE RESIDENCIAS
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy import Text, ForeignKey, DateTime, func
from datetime import datetime
from typing import Optional

from .base import Base

class Residence(Base):
    """
    Modelo de Residencia para el sistema de gestión de residencias.
    Representa una residencia donde viven los residentes y trabajan los profesionales.
    """
    __tablename__ = "residence"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Contacto (encriptado) ----------
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la residencia."""
        return f"<Residence(id={self.id[:8]}..., name={self.name})>"

    def __str__(self) -> str:
        """Representación legible de la residencia."""
        return f"Residencia {self.name}"

    @property
    def is_active(self) -> bool:
        """
        Verifica si la residencia está activa.
        Una residencia está activa si no ha sido eliminada (soft delete).
        """
        return self.deleted_at is None

    @property
    def contact_info(self) -> dict:
        """
        Devuelve un diccionario con la información de contacto.
        Note: Los campos están encriptados, requieren desencriptación.
        """
        return {
            "phone_encrypted": self.phone_encrypted,
            "email_encrypted": self.email_encrypted
        }


class UserResidence(Base):
    """
    Modelo de relación entre Usuarios y Residencias.
    Tabla de asociación que define qué usuarios tienen acceso a qué residencias.
    """
    __tablename__ = "user_residence"

    # ---------- Claves primarias compuestas ----------
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True
    )
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="CASCADE"),
        primary_key=True
    )

    def __repr__(self) -> str:
        """Representación en string de la relación usuario-residencia."""
        return f"<UserResidence(user_id={self.user_id[:8]}..., residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la relación usuario-residencia."""
        return f"Asignación: Usuario {self.user_id[:8]}... → Residencia {self.residence_id[:8]}..."