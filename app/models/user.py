# =====================================================================
# MODELO DE USUARIOS
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy import Text, DateTime, func
from datetime import datetime
from typing import Optional

from .base import Base, user_role_enum

class User(Base):
    """
    Modelo de Usuario para el sistema de residencias.
    Representa a los usuarios del sistema con diferentes roles y permisos.
    """
    __tablename__ = "user"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    role: Mapped[str] = mapped_column(user_role_enum, nullable=False)

    # ---------- Datos de autenticación ----------
    alias_encrypted: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    alias_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Contacto (encriptado) ----------
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(BYTEA)

    # ---------- Auditoría ----------
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string del usuario."""
        return f"<User(id={self.id[:8]}..., role={self.role})>"

    def __str__(self) -> str:
        """Representación legible del usuario."""
        return f"Usuario {self.alias_hash[:8]}... ({self.role})"

    @property
    def is_active(self) -> bool:
        """
        Verifica si el usuario está activo.
        Un usuario está activo si no ha sido eliminado (soft delete).
        """
        return self.deleted_at is None

    @property
    def is_superadmin(self) -> bool:
        """Verifica si el usuario tiene rol de superadministrador."""
        return self.role == "superadmin"

    @property
    def is_manager(self) -> bool:
        """Verifica si el usuario tiene rol de gerente."""
        return self.role == "manager"

    @property
    def is_professional(self) -> bool:
        """Verifica si el usuario tiene rol de profesional."""
        return self.role == "professional"