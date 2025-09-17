# =====================================================================
# MODELO DE REGISTRO DE EVENTOS DEL SISTEMA
# =====================================================================

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Text, Integer, ForeignKey, DateTime, func
from datetime import datetime
from typing import Optional, Dict

from .base import Base

class EventLog(Base):
    """
    Modelo de Registro de Eventos para el sistema de residencias.
    Registra todas las acciones importantes realizadas en el sistema para auditoría.
    """
    __tablename__ = "event_log"

    # ---------- Identificación ----------
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---------- Actor y contexto ----------
    actor_user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("user.id"))
    residence_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("residence.id"))

    # ---------- Información del evento ----------
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    action: Mapped[str] = mapped_column(Text, nullable=False)

    # ---------- Timestamps ----------
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---------- Metadatos adicionales ----------
    meta: Mapped[Optional[Dict]] = mapped_column(JSONB)

    def __repr__(self) -> str:
        """Representación en string del evento."""
        return f"<EventLog(id={self.id}, action={self.action}, entity={self.entity})>"

    def __str__(self) -> str:
        """Representación legible del evento."""
        actor_info = f"Usuario {self.actor_user_id[:8]}..." if self.actor_user_id else "Sistema"
        return f"{actor_info} {self.action} {self.entity}"

    @property
    def event_info(self) -> dict:
        """
        Devuelve un diccionario con la información completa del evento.
        Returns:
            dict: Información estructurada del evento
        """
        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "residence_id": self.residence_id,
            "entity": self.entity,
            "entity_id": self.entity_id,
            "action": self.action,
            "at": self.at,
            "meta": self.meta
        }

    @property
    def human_readable_action(self) -> str:
        """
        Devuelve una descripción legible de la acción en español.
        Returns:
            str: Descripción de la acción en español
        """
        action_map = {
            "create": "creó",
            "update": "actualizó",
            "delete": "eliminó",
            "read": "consultó",
            "login": "inició sesión",
            "logout": "cerró sesión",
            "assign": "asignó",
            "unassign": "desasignó",
            "approve": "aprobó",
            "reject": "rechazó",
            "complete": "completó",
            "cancel": "canceló"
        }
        return action_map.get(self.action, self.action)

    @property
    def human_readable_entity(self) -> str:
        """
        Devuelve una descripción legible de la entidad en español.
        Returns:
            str: Descripción de la entidad en español
        """
        entity_map = {
            "user": "usuario",
            "resident": "residente",
            "residence": "residencia",
            "floor": "piso",
            "room": "habitación",
            "bed": "cama",
            "device": "dispositivo",
            "task": "tarea",
            "measurement": "medición",
            "tag": "etiqueta"
        }
        return entity_map.get(self.entity, self.entity)

    @property
    def formatted_description(self) -> str:
        """
        Devuelve una descripción formateada del evento.
        Returns:
            str: Descripción completa y legible del evento
        """
        actor = f"Usuario {self.actor_user_id[:8]}..." if self.actor_user_id else "Sistema"
        action = self.human_readable_action
        entity = self.human_readable_entity

        description = f"{actor} {action} {entity}"

        if self.entity_id:
            description += f" (ID: {self.entity_id[:8]}...)"

        if self.residence_id:
            description += f" en residencia {self.residence_id[:8]}..."

        return description

    @property
    def is_system_event(self) -> bool:
        """
        Verifica si el evento fue generado por el sistema.
        Returns:
            bool: True si es un evento del sistema, False si fue generado por un usuario
        """
        return self.actor_user_id is None

    @property
    def is_security_related(self) -> bool:
        """
        Verifica si el evento está relacionado con seguridad.
        Returns:
            bool: True si es un evento de seguridad, False en caso contrario
        """
        security_actions = {"login", "logout", "create", "delete", "update"}
        security_entities = {"user", "residence"}
        return self.action in security_actions or self.entity in security_entities

    @property
    def event_age(self) -> Optional[datetime.timedelta]:
        """
        Devuelve el tiempo transcurrido desde que ocurrió el evento.
        Returns:
            Optional[datetime.timedelta]: Tiempo transcurrido o None si el evento no tiene timestamp
        """
        if self.at:
            return datetime.now(self.at.tzinfo) - self.at
        return None