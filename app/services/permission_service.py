"""
Servicio centralizado para validación de permisos basado en roles
"""
from typing import List, Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models import User, UserResidence, Residence, Resident, Device, TaskApplication

class PermissionService:
    """Servicio para gestionar permisos y acceso basado en roles"""

    @staticmethod
    async def get_user_residences(db: AsyncSession, user_id: str) -> List[str]:
        """Obtener IDs de residencias asignadas a un usuario"""
        result = await db.execute(
            select(UserResidence.residence_id)
            .where(UserResidence.user_id == user_id)
        )
        return [row[0] for row in result.fetchall()]

    @staticmethod
    async def can_access_residence(db: AsyncSession, user_id: str, residence_id: str, user_role: str) -> bool:
        """Verificar si un usuario puede acceder a una residencia específica"""
        if user_role == "superadmin":
            return True

        # Verificar si la residencia está asignada al usuario
        result = await db.execute(
            select(UserResidence)
            .where(
                UserResidence.user_id == user_id,
                UserResidence.residence_id == residence_id
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_accessible_residence_ids(db: AsyncSession, user_id: str, user_role: str) -> List[str]:
        """Obtener IDs de residencias accesibles para un usuario"""
        if user_role == "superadmin":
            # Superadmin puede acceder a todas las residencias
            result = await db.execute(select(Residence.id).where(Residence.deleted_at.is_(None)))
            return [row[0] for row in result.fetchall()]

        # Otros roles solo ven sus residencias asignadas
        return await PermissionService.get_user_residences(db, user_id)

    @staticmethod
    async def validate_residence_access(db: AsyncSession, user_id: str, residence_id: str, user_role: str) -> None:
        """Validar acceso a una residencia y lanzar excepción si no tiene permiso"""
        if not await PermissionService.can_access_residence(db, user_id, residence_id, user_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permiso para acceder a esta residencia"
            )

    @staticmethod
    def can_manage_residences(user_role: str) -> bool:
        """Verificar si un rol puede gestionar residencias"""
        return user_role == "superadmin"

    @staticmethod
    def can_manage_users(user_role: str, target_role: str) -> bool:
        """Verificar si un rol puede gestionar usuarios según el rol objetivo"""
        if user_role == "superadmin":
            return True

        if user_role == "manager" and target_role in {"manager", "professional"}:
            return True

        return False

    @staticmethod
    def can_create_resident(user_role: str) -> bool:
        """Verificar si un rol puede crear residentes"""
        return user_role in ["superadmin", "manager"]

    @staticmethod
    def can_manage_all_tasks(user_role: str) -> bool:
        """Verificar si un rol puede gestionar todas las tareas"""
        return user_role in ["superadmin", "manager"]

    @staticmethod
    async def filter_query_by_residence(query, db: AsyncSession, user_id: str, user_role: str, residence_id: Optional[str] = None):
        """
        Filtrar una consulta por residencias accesibles del usuario

        Args:
            query: Consulta SQLAlchemy a filtrar
            db: Sesión de base de datos
            user_id: ID del usuario actual
            user_role: Rol del usuario actual
            residence_id: ID específico de residencia (opcional)
        """
        # Obtener residencias accesibles para el usuario
        accessible_residences = await PermissionService.get_accessible_residence_ids(db, user_id, user_role)

        if residence_id:
            # Si se especifica una residencia, verificar acceso y filtrar por esa
            await PermissionService.validate_residence_access(db, user_id, residence_id, user_role)
            # Resident ya está importado al inicio del archivo
            return query.where(Resident.residence_id == residence_id)
        else:
            # Si no se especifica, filtrar por todas las residencias accesibles
            if accessible_residences:
                # Resident ya está importado al inicio del archivo
                return query.where(Resident.residence_id.in_(accessible_residences))
            else:
                # Si no tiene residencias asignadas, retornar consulta vacía
                return query.where(text("1=0"))
