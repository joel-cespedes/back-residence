# =====================================================================
# ENDPOINTS DE USUARIOS - CRUD COMPLETO
# =====================================================================

from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, text, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.models import User, UserResidence, Residence
from app.schemas import (
    UserCreate, UserOut, UserResidenceAssignment,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid, decrypt_data, encrypt_data, hash_alias
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/users", tags=["users"])

# =====================================================================
# FUNCIONES AUXILIARES
# =====================================================================

def _hash_password(password: str) -> str:
    """Hash de contraseña usando bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

async def _ensure_alias_available(db: AsyncSession, alias_hash: str, exclude_user_id: str = None):
    """Verifica que el alias esté disponible"""
    query = select(User).where(User.alias_hash == alias_hash, User.deleted_at.is_(None))
    
    # Excluir el usuario actual si se está actualizando
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Alias already exists")

async def _validate_residences_exist(db: AsyncSession, residence_ids: list[str]) -> list[str]:
    """Valida que las residencias existan"""
    if not residence_ids:
        return []
    
    result = await db.execute(
        select(Residence.id).where(
            Residence.id.in_(residence_ids),
            Residence.deleted_at.is_(None)
        )
    )
    valid_ids = [row[0] for row in result.fetchall()]
    
    invalid_ids = set(residence_ids) - set(valid_ids)
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid residence IDs: {list(invalid_ids)}"
        )
    
    return valid_ids

async def _validate_assignment_scope(db: AsyncSession, user_role: str, user_id: str, residence_ids: list[str]):
    """Valida que el usuario pueda asignar estas residencias"""
    if user_role == "superadmin":
        return  # Superadmin puede asignar cualquier residencia
    
    # Otros roles solo pueden asignar residencias que tengan asignadas
    accessible_residences = await PermissionService.get_accessible_residence_ids(db, user_id, user_role)
    
    invalid_assignments = set(residence_ids) - set(accessible_residences)
    if invalid_assignments:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot assign residences: {list(invalid_assignments)}"
        )

# =====================================================================
# ENDPOINTS CRUD
# =====================================================================

@router.get("/", response_model=PaginatedResponse)
async def list_users(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    role: str = Query(None, description="Filter by role: manager, professional"),
):
    """List users with pagination and role-based filtering"""
    
    # Build base query
    base_query = select(User).where(User.deleted_at.is_(None))
    
    # Apply role filter if provided
    if role:
        if role not in ["manager", "professional"]:
            raise HTTPException(status_code=400, detail="Invalid role filter")
        base_query = base_query.where(User.role == role)
    else:
        # Exclude superadmin from general listing
        base_query = base_query.where(User.role.in_(["manager", "professional"]))
    
    # Apply permission-based filtering
    if current["role"] != "superadmin":
        # Managers can see:
        # 1. Managers they created themselves
        # 2. Professionals from their assigned residences
        accessible_residences = await PermissionService.get_accessible_residence_ids(
            db, current["id"], current["role"]
        )
        
        if not accessible_residences:
            # No residences = no users visible
            return PaginatedResponse(
                items=[], 
                total=0, 
                page=pagination.page, 
                size=pagination.size,
                pages=0,
                has_next=False,
                has_prev=False
            )
        
        # Filter: managers created by current user OR professionals from accessible residences
        base_query = base_query.where(
            or_(
                and_(User.role == "manager", User.created_by == current["id"]),
                and_(User.role == "professional", User.id.in_(
                    select(UserResidence.user_id).where(
                        UserResidence.residence_id.in_(accessible_residences),
                        UserResidence.deleted_at.is_(None)
                    )
                ))
            )
        )
    
    # Apply search filter if provided
    if filters.search:
        # Search by name if available
        base_query = base_query.where(User.name.ilike(f"%{filters.search}%"))
    
    # Get total count
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar()
    
    # Apply pagination and sorting
    if pagination.sort_by == "created_at":
        if pagination.sort_order == "desc":
            base_query = base_query.order_by(User.created_at.desc())
        else:
            base_query = base_query.order_by(User.created_at.asc())
    elif pagination.sort_by == "name":
        if pagination.sort_order == "desc":
            base_query = base_query.order_by(User.name.desc())
        else:
            base_query = base_query.order_by(User.name.asc())
    
    base_query = base_query.offset((pagination.page - 1) * pagination.size).limit(pagination.size)
    
    # Execute query
    result = await db.execute(base_query)
    users = result.scalars().all()
    
    # Get residence assignments and creator info for each user
    items = []
    for user in users:
        # Get user's residence assignments with names
        residence_query = (
            select(Residence.id, Residence.name)
            .join(UserResidence, UserResidence.residence_id == Residence.id)
            .where(UserResidence.user_id == user.id, Residence.deleted_at.is_(None))
        )
        
        # If current user is not superadmin, filter residences by their accessible residences
        if current["role"] != "superadmin":
            accessible_residences = await PermissionService.get_accessible_residence_ids(
                db, current["id"], current["role"]
            )
            residence_query = residence_query.where(Residence.id.in_(accessible_residences))
        
        residence_result = await db.execute(residence_query)
        residences = [{"id": row[0], "name": row[1]} for row in residence_result.fetchall()]
        
        # Get creator info
        created_by_info = None
        if user.created_by:
            creator_result = await db.execute(
                select(User.name, User.alias_encrypted).where(User.id == user.created_by)
            )
            creator = creator_result.first()
            if creator:
                creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
                created_by_info = {
                    "id": user.created_by,
                    "name": creator[0],
                    "alias": creator_alias
                }
        
        # Decrypt alias for display
        alias_display = decrypt_data(user.alias_encrypted) if user.alias_encrypted else "N/A"
        
        items.append({
            "id": user.id,
            "alias": alias_display,
            "name": user.name,
            "role": user.role,
            "residences": residences,  # Ahora con nombres
            "created_by": created_by_info,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        })
    
    # Calculate pagination metadata
    pages = (total + pagination.size - 1) // pagination.size  # Ceiling division
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )

@router.get("/{user_id}", response_model=dict)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get a specific user by ID"""
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions
    if current["role"] != "superadmin":
        # Managers can see:
        # 1. Managers they created themselves
        # 2. Professionals from their assigned residences
        if user.role == "manager":
            # Can only see managers they created
            if user.created_by != current["id"]:
                raise HTTPException(status_code=403, detail="Access denied to this user")
        elif user.role == "professional":
            # Can see professionals from their assigned residences
            accessible_residences = await PermissionService.get_accessible_residence_ids(
                db, current["id"], current["role"]
            )
            
            # Check if this professional is assigned to any of the manager's residences
            user_residences = await db.execute(
                select(UserResidence.residence_id).where(
                    UserResidence.user_id == user.id,
                    UserResidence.deleted_at.is_(None)
                )
            )
            user_residence_ids = [row[0] for row in user_residences.fetchall()]
            
            if not any(rid in accessible_residences for rid in user_residence_ids):
                raise HTTPException(status_code=403, detail="Access denied to this user")
    
    # Get user's residence assignments with names
    residence_query = (
        select(Residence.id, Residence.name)
        .join(UserResidence, UserResidence.residence_id == Residence.id)
        .where(UserResidence.user_id == user.id, Residence.deleted_at.is_(None))
    )
    
    # If current user is not superadmin, filter residences by their accessible residences
    if current["role"] != "superadmin":
        accessible_residences = await PermissionService.get_accessible_residence_ids(
            db, current["id"], current["role"]
        )
        residence_query = residence_query.where(Residence.id.in_(accessible_residences))
    
    residence_result = await db.execute(residence_query)
    residences = [{"id": row[0], "name": row[1]} for row in residence_result.fetchall()]
    
    # Get creator info
    created_by_info = None
    if user.created_by:
        creator_result = await db.execute(
            select(User.name, User.alias_encrypted).where(User.id == user.created_by)
        )
        creator = creator_result.first()
        if creator:
            creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
            created_by_info = {
                "id": user.created_by,
                "name": creator[0],
                "alias": creator_alias
            }
    
    # Decrypt alias for display
    alias_display = decrypt_data(user.alias_encrypted) if user.alias_encrypted else "N/A"
    
    return {
        "id": user.id,
        "alias": alias_display,
        "name": user.name,
        "role": user.role,
        "residences": residences,
        "created_by": created_by_info,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Create a new user with proper audit trail"""
    target_role = payload.role

    alias_input = payload.alias.strip()
    if not alias_input:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Alias cannot be empty")

    if not PermissionService.can_manage_users(current["role"], target_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted for role")

    if target_role in {"manager", "professional"} and not payload.residence_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Residence assignments required")

    alias_hash = hash_alias(alias_input)
    await _ensure_alias_available(db, alias_hash)

    unique_residences: list[str] = []
    seen: set[str] = set()
    for residence_id in payload.residence_ids:
        if residence_id not in seen:
            unique_residences.append(residence_id)
            seen.add(residence_id)

    valid_residences = await _validate_residences_exist(db, unique_residences)
    await _validate_assignment_scope(db, current["role"], current["id"], valid_residences)

    password_hash = _hash_password(payload.password)
    user = User(
        id=new_uuid(),
        role=target_role,
        alias_encrypted=encrypt_data(alias_input),
        alias_hash=alias_hash,
        password_hash=password_hash,
        name=payload.name,
        created_by=current["id"],  # Siempre llenar con el usuario actual
    )

    db.add(user)
    await db.flush()

    assignments: list[UserResidence] = []
    for residence_id in valid_residences:
        assignment = UserResidence(user_id=user.id, residence_id=residence_id)
        db.add(assignment)
        assignments.append(assignment)

    await db.commit()
    await db.refresh(user)

    return UserOut(
        id=user.id,
        alias=alias_input,
        role=user.role,
        residences=[UserResidenceAssignment(id=a.residence_id) for a in assignments],
        created_at=user.created_at,
    )

@router.put("/{user_id}", response_model=dict)
async def update_user(
    user_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a user and their residence assignments"""
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions to manage this user
    if current["role"] != "superadmin":
        # Managers can manage:
        # 1. Managers they created themselves
        # 2. Professionals from their assigned residences
        if user.role == "manager":
            # Can only manage managers they created
            if user.created_by != current["id"]:
                raise HTTPException(status_code=403, detail="Access denied to this user")
        elif user.role == "professional":
            # Can manage professionals from their assigned residences
            accessible_residences = await PermissionService.get_accessible_residence_ids(
                db, current["id"], current["role"]
            )
            
            # Check if this professional is assigned to any of the manager's residences
            user_residences = await db.execute(
                select(UserResidence.residence_id).where(
                    UserResidence.user_id == user.id,
                    UserResidence.deleted_at.is_(None)
                )
            )
            user_residence_ids = [row[0] for row in user_residences.fetchall()]
            
            if not any(rid in accessible_residences for rid in user_residence_ids):
                raise HTTPException(status_code=403, detail="Access denied to this user")
    
    if not PermissionService.can_manage_users(current["role"], user.role):
        raise HTTPException(status_code=403, detail="Cannot manage this user type")
    
    # Validate residence assignments if provided
    new_residence_ids = payload.get("residence_ids", [])
    if new_residence_ids:
        # Validate residences exist
        valid_residences = await _validate_residences_exist(db, new_residence_ids)
        
        # Check assignment scope
        await _validate_assignment_scope(db, current["role"], current["id"], valid_residences)
    
    # Update fields if provided
    if "name" in payload and payload["name"]:
        user.name = payload["name"]
    
    if "alias" in payload and payload["alias"]:
        new_alias = payload["alias"].strip()
        current_alias = decrypt_data(user.alias_encrypted) if user.alias_encrypted else ""
        
        print(f"DEBUG: Raw alias_encrypted: {user.alias_encrypted}")
        print(f"DEBUG: Decrypted current alias: '{current_alias}'")
        print(f"DEBUG: New alias from payload: '{new_alias}'")
        print(f"DEBUG: Are they equal? {new_alias == current_alias}")
        
        if new_alias != current_alias:
            print(f"DEBUG: Alias diferente, procediendo con el cambio")
            # Verificar que el nuevo alias esté disponible
            new_alias_hash = hash_alias(new_alias)
            await _ensure_alias_available(db, new_alias_hash, user.id)
            
            # Actualizar alias
            user.alias_encrypted = encrypt_data(new_alias)
            user.alias_hash = new_alias_hash
            print(f"DEBUG: Alias actualizado en el modelo")
        else:
            print(f"DEBUG: Alias no cambió, es el mismo")
    
    if "password" in payload and payload["password"]:
        user.password_hash = _hash_password(payload["password"])
    
    # Update residence assignments if provided
    if "residence_ids" in payload:
        # Remove existing assignments
        await db.execute(
            text("DELETE FROM user_residence WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        
        # Add new assignments
        for residence_id in new_residence_ids:
            assignment = UserResidence(user_id=user_id, residence_id=residence_id)
            db.add(assignment)
    
    await db.commit()
    await db.refresh(user)
    
    # Get updated residence assignments
    residence_result = await db.execute(
        select(Residence.id, Residence.name)
        .join(UserResidence, UserResidence.residence_id == Residence.id)
        .where(UserResidence.user_id == user.id, Residence.deleted_at.is_(None))
    )
    residences = [{"id": row[0], "name": row[1]} for row in residence_result.fetchall()]
    
    # Get creator info
    created_by_info = None
    if user.created_by:
        creator_result = await db.execute(
            select(User.name, User.alias_encrypted).where(User.id == user.created_by)
        )
        creator = creator_result.first()
        if creator:
            creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
            created_by_info = {
                "id": user.created_by,
                "name": creator[0],
                "alias": creator_alias
            }
    
    # Decrypt alias for display
    alias_display = decrypt_data(user.alias_encrypted) if user.alias_encrypted else "N/A"
    
    return {
        "id": user.id,
        "alias": alias_display,
        "name": user.name,
        "role": user.role,
        "residences": residences,
        "created_by": created_by_info,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Soft delete a user"""
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions
    if not PermissionService.can_manage_users(current["role"], user.role):
        raise HTTPException(status_code=403, detail="Cannot delete this user type")
    
    # Prevent self-deletion
    if user.id == current["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # Soft delete
    user.deleted_at = func.now()
    
    await db.commit()