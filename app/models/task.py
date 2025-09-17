# =====================================================================
# MODELOS DE TAREAS Y CATEGORÍAS
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Text, SmallInteger, Boolean, ForeignKey, DateTime, func
from datetime import datetime
from typing import Optional

from .base import Base

class TaskCategory(Base):
    """
    Modelo de Categoría de Tareas para el sistema de residencias.
    Representa las categorías en las que se organizan las tareas.
    Las categorías son únicas por residencia.
    """
    __tablename__ = "task_category"

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
        """Representación en string de la categoría de tarea."""
        return f"<TaskCategory(id={self.id[:8]}..., name={self.name}, residence_id={self.residence_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la categoría de tarea."""
        return f"Categoría: {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la categoría está activa (no eliminada)."""
        return self.deleted_at is None


class TaskTemplate(Base):
    """
    Modelo de Plantilla de Tarea para el sistema de residencias.
    Representa las plantillas de tareas que pueden ser asignadas a residentes.
    """
    __tablename__ = "task_template"

    # ---------- Identificación ----------
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    residence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("residence.id", ondelete="RESTRICT"),
        nullable=False
    )
    task_category_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("task_category.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Estados posibles de la tarea ----------
    status1: Mapped[Optional[str]] = mapped_column(Text)
    status2: Mapped[Optional[str]] = mapped_column(Text)
    status3: Mapped[Optional[str]] = mapped_column(Text)
    status4: Mapped[Optional[str]] = mapped_column(Text)
    status5: Mapped[Optional[str]] = mapped_column(Text)
    status6: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Configuración adicional ----------
    audio_phrase: Mapped[Optional[str]] = mapped_column(Text)
    is_block: Mapped[Optional[bool]] = mapped_column(Boolean)

    # ---------- Auditoría ----------
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la plantilla de tarea."""
        return f"<TaskTemplate(id={self.id[:8]}..., name={self.name}, category_id={self.task_category_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la plantilla de tarea."""
        return f"Plantilla: {self.name}"

    @property
    def is_active(self) -> bool:
        """Verifica si la plantilla está activa (no eliminada)."""
        return self.deleted_at is None

    @property
    def available_statuses(self) -> list[str]:
        """
        Devuelve una lista de los estados disponibles para esta tarea.
        Returns:
            list[str]: Lista de estados configurados para la tarea
        """
        statuses = []
        for i in range(1, 7):
            status = getattr(self, f"status{i}", None)
            if status:
                statuses.append(status)
        return statuses


class TaskApplication(Base):
    """
    Modelo de Aplicación de Tarea para el sistema de residencias.
    Representa la asignación de una plantilla de tarea a un residente específico.
    """
    __tablename__ = "task_application"

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
    task_template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("task_template.id", ondelete="RESTRICT"),
        nullable=False
    )

    # ---------- Aplicación ----------
    applied_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---------- Estado de la aplicación ----------
    selected_status_index: Mapped[Optional[int]] = mapped_column(SmallInteger)
    selected_status_text: Mapped[Optional[str]] = mapped_column(Text)

    # ---------- Auditoría ----------
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        """Representación en string de la aplicación de tarea."""
        return f"<TaskApplication(id={self.id[:8]}..., resident_id={self.resident_id[:8]}...)>"

    def __str__(self) -> str:
        """Representación legible de la aplicación de tarea."""
        return f"Tarea aplicada a residente {self.resident_id[:8]}..."

    @property
    def is_active(self) -> bool:
        """Verifica si la aplicación está activa (no eliminada)."""
        return self.deleted_at is None

    @property
    def current_status(self) -> Optional[str]:
        """
        Devuelve el estado actual de la aplicación.
        Returns:
            Optional[str]: Estado actual o None si no hay estado seleccionado
        """
        return self.selected_status_text

    @property
    def is_completed(self) -> bool:
        """
        Verifica si la tarea está completada.
        Considera completada si tiene un estado seleccionado.
        Returns:
            bool: True si está completada, False en caso contrario
        """
        return self.selected_status_text is not None