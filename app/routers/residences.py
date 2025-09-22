# app/routers/residences.py
from __future__ import annotations

import bcrypt

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_db, get_current_user
from app.models import Residence, User, UserResidence
from app.schemas import (
    ResidenceCreate, ResidenceUpdate, ResidenceOut,
    PaginationParams, PaginatedResponse, FilterParams,
    UserCreate, UserOut, UserResidenceAssignment,
)
from app.security import new_uuid, decrypt_data, encrypt_data, hash_alias
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/residences", tags=["residences"])
user_router = APIRouter(prefix="/users", tags=["users"])

# -------------------- Helper Functions --------------------

async def get_residence_or_404(id: str, db: AsyncSession) -> Residence:
    """Get residence by ID or raise 404"""
    result = await db.execute(
        select(Residence).where(Residence.id == id, Residence.deleted_at.is_(None))
    )
    residence = result.scalar_one_or_none()
    if not residence:
        raise HTTPException(status_code=404, detail="Residence not found")
    return residence

async def apply_residence_context(db: AsyncSession, current: dict, residence_id: str | None):
    """Apply residence context for RLS"""
    if residence_id:
        if current["role"] != "superadmin":
            # Check if user has access to this residence
            result = await db.execute(
                select(UserResidence).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.residence_id == residence_id,
                )
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail="Access denied to this residence")

        await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": residence_id})
    elif current["role"] != "superadmin":
        raise HTTPException(status_code=400, detail="Residence ID required for non-superadmin users")

async def paginate_query(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse:
    """Apply pagination and filters to a query"""

    # Apply filters
    if filter_params:
        if filter_params.date_from:
            query = query.where(Residence.created_at >= filter_params.date_from)
        if filter_params.date_to:
            query = query.where(Residence.created_at <= filter_params.date_to)
        if getattr(filter_params, 'search', None):
            search_term = f"%{getattr(filter_params, 'search', '')}%"
            query = query.where(or_(
                Residence.name.ilike(search_term),
                Residence.address.ilike(search_term)
            ))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply sorting
    if pagination.sort_by:
        sort_field = getattr(Residence, pagination.sort_by, Residence.created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(Residence.created_at.desc())

    # Apply pagination
    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)

    # Execute query
    result = await db.execute(query)
    items = []
    for row in result.scalars().all():
        # Desencriptar datos de contacto
        phone = decrypt_data(row.phone_encrypted) if row.phone_encrypted else 'No especificado'
        email = decrypt_data(row.email_encrypted) if row.email_encrypted else 'No especificado'

        item = {
            'id': row.id,
            'name': row.name,
            'address': row.address,
            'phone': phone,
            'email': email,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }
        items.append(item)

    # Calculate pagination metadata
    pages = (total + pagination.size - 1) // pagination.size
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


# -------------------- User Management --------------------


async def _ensure_alias_available(db: AsyncSession, alias_hash: str) -> None:
    """Valida que el alias no esté en uso."""

    result = await db.execute(
        select(User).where(User.alias_hash == alias_hash, User.deleted_at.is_(None))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alias already in use")


async def _validate_residences_exist(db: AsyncSession, residence_ids: list[str]) -> list[str]:
    """Confirma que las residencias existen y están activas (preserva orden)."""

    if not residence_ids:
        return []

    result = await db.execute(
        select(Residence.id).where(Residence.id.in_(residence_ids), Residence.deleted_at.is_(None))
    )
    found = {row[0] for row in result.fetchall()}
    missing = set(residence_ids) - found
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Residence not found")

    return [rid for rid in residence_ids if rid in found]


async def _validate_assignment_scope(
    db: AsyncSession,
    creator_role: str,
    creator_id: str,
    residence_ids: list[str],
) -> None:
    """Evita que un gestor asigne residencias que no le pertenecen."""

    if creator_role == "superadmin" or not residence_ids:
        return

    allowed = set(await PermissionService.get_user_residences(db, creator_id))
    if not set(residence_ids).issubset(allowed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign unowned residences")


def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


@user_router.get("/", response_model=PaginatedResponse)
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
        # Managers can only see users in their assigned residences
        accessible_residences = await PermissionService.get_accessible_residence_ids(
            db, current["id"], current["role"]
        )
        
        if not accessible_residences:
            # No residences = no users visible
            return PaginatedResponse(items=[], total=0, page=pagination.page, size=pagination.size)
        
        # Join with UserResidence to filter by accessible residences
        base_query = base_query.join(UserResidence, UserResidence.user_id == User.id).where(
            UserResidence.residence_id.in_(accessible_residences)
        ).distinct()
    
    # Apply search filter if provided
    if filters.search:
        # Since alias is encrypted, we can't search by it directly
        # We'll search by role for now
        base_query = base_query.where(User.role.ilike(f"%{filters.search}%"))
    
    # Get total count
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar()
    
    # Apply pagination and sorting
    if pagination.sort_by == "created_at":
        if pagination.sort_order == "desc":
            base_query = base_query.order_by(User.created_at.desc())
        else:
            base_query = base_query.order_by(User.created_at.asc())
    
    base_query = base_query.offset((pagination.page - 1) * pagination.size).limit(pagination.size)
    
    # Execute query
    result = await db.execute(base_query)
    users = result.scalars().all()
    
    # Get residence assignments for each user
    items = []
    for user in users:
        # Get user's residence assignments
        residence_result = await db.execute(
            select(UserResidence.residence_id).where(UserResidence.user_id == user.id)
        )
        residence_ids = [row[0] for row in residence_result.fetchall()]
        
        # Decrypt alias for display
        alias = decrypt_data(user.alias_encrypted) if user.alias_encrypted else "N/A"
        
        items.append({
            "id": user.id,
            "alias": alias,
            "role": user.role,
            "residence_ids": residence_ids,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        })
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size
    )

@user_router.get("/{user_id}", response_model=dict)
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
        # Managers can only see users in their accessible residences
        user_residences = await db.execute(
            select(UserResidence.residence_id).where(UserResidence.user_id == user.id)
        )
        user_residence_ids = [row[0] for row in user_residences.fetchall()]
        
        accessible_residences = await PermissionService.get_accessible_residence_ids(
            db, current["id"], current["role"]
        )
        
        # Check if there's any overlap
        if not any(rid in accessible_residences for rid in user_residence_ids):
            raise HTTPException(status_code=403, detail="Access denied to this user")
    
    # Get user's residence assignments with names
    residence_result = await db.execute(
        select(Residence.id, Residence.name)
        .join(UserResidence, UserResidence.residence_id == Residence.id)
        .where(UserResidence.user_id == user.id, Residence.deleted_at.is_(None))
    )
    residences = [{"id": row[0], "name": row[1]} for row in residence_result.fetchall()]
    
    # Decrypt alias
    alias = decrypt_data(user.alias_encrypted) if user.alias_encrypted else "N/A"
    
    return {
        "id": user.id,
        "alias": alias,
        "role": user.role,
        "residences": residences,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

@user_router.put("/{user_id}", response_model=dict)
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
    if not PermissionService.can_manage_users(current["role"], user.role):
        raise HTTPException(status_code=403, detail="Cannot manage this user type")
    
    # Validate residence assignments if provided
    new_residence_ids = payload.get("residence_ids", [])
    if new_residence_ids:
        # Validate residences exist
        valid_residences = await _validate_residences_exist(db, new_residence_ids)
        
        # Check assignment scope
        await _validate_assignment_scope(db, current["role"], current["id"], valid_residences)
    
    # Update password if provided
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
    
    alias = decrypt_data(user.alias_encrypted) if user.alias_encrypted else "N/A"
    
    return {
        "id": user.id,
        "alias": alias,
        "role": user.role,
        "residences": residences,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

@user_router.delete("/{user_id}", status_code=204)
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

@user_router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
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

# -------------------- CRUD Endpoints --------------------

@router.post("/", response_model=ResidenceOut, status_code=201)
async def create_residence(
    data: ResidenceCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Create a new residence (superadmin only)"""
    if current["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can create residences")

    # Check for duplicate name
    existing = await db.scalar(
        select(Residence.id).where(
            Residence.name == data.name,
            Residence.deleted_at.is_(None)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Residence name already exists")

    # Set user context for triggers
    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    residence = Residence(
        id=new_uuid(),
        name=data.name,
        address=data.address,
        created_by=current["id"]
    )

    # Handle encrypted fields if provided
    if data.phone:
        residence.phone_encrypted = encrypt_data(data.phone)
    if data.email:
        residence.email_encrypted = encrypt_data(data.email)

    db.add(residence)
    await db.commit()
    await db.refresh(residence)
    return residence

@router.get("/", response_model=PaginatedResponse)
async def list_residences(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="residence_id"),
):
    """List residences with pagination and filters"""
    await apply_residence_context(db, current, residence_id)

    # Build base query based on user role
    if current["role"] == "superadmin":
        query = select(Residence).where(Residence.deleted_at.is_(None))
    else:
        # Only show residences the user has access to
        query = (
            select(Residence)
            .join(UserResidence, UserResidence.residence_id == Residence.id)
            .where(
                UserResidence.user_id == current["id"],
                Residence.deleted_at.is_(None)
            )
        )

    return await paginate_query(query, db, pagination, filters)

@router.get("/mine", response_model=list[dict])
async def my_residences(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get residences assigned to current user"""
    if current["role"] == "superadmin":
        result = await db.execute(
            select(Residence.id, Residence.name)
            .where(Residence.deleted_at.is_(None))
            .order_by(Residence.name)
        )
    else:
        result = await db.execute(
            select(Residence.id, Residence.name)
            .join(UserResidence, UserResidence.residence_id == Residence.id)
            .where(
                UserResidence.user_id == current["id"],
                Residence.deleted_at.is_(None)
            )
            .order_by(Residence.name)
        )
    return [{"id": rid, "name": name} for (rid, name) in result.all()]

@router.get("/{id}", response_model=ResidenceOut)
async def get_residence(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get a specific residence"""
    residence = await get_residence_or_404(id, db)

    # Check access permissions
    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this residence")

    return residence

@router.put("/{id}", response_model=ResidenceOut)
async def update_residence(
    id: str,
    data: ResidenceUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a residence"""
    residence = await get_residence_or_404(id, db)

    # Check permissions
    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this residence")

    # Set user context for triggers
    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    # Update fields
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field not in ['phone', 'email']:  # Handle encrypted fields separately
            setattr(residence, field, value)

    # Handle encrypted fields if provided
    if 'phone' in update_data:
        residence.phone_encrypted = encrypt_data(update_data['phone']) if update_data['phone'] else None
    if 'email' in update_data:
        residence.email_encrypted = encrypt_data(update_data['email']) if update_data['email'] else None

    await db.commit()
    await db.refresh(residence)
    return residence

@router.delete("/{id}", status_code=204)
async def delete_residence(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Soft delete a residence (superadmin only)"""
    if current["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can delete residences")

    residence = await get_residence_or_404(id, db)

    # Set user context for triggers
    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    residence.deleted_at = func.now()
    await db.commit()

# -------------------- Additional Endpoints --------------------

@router.get("/{id}/users", response_model=list[dict])
async def get_residence_users(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get users assigned to a residence"""
    # Check permissions
    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this residence")

    await get_residence_or_404(id, db)

    result = await db.execute(
        select(User)
        .join(UserResidence, UserResidence.user_id == User.id)
        .where(
            UserResidence.residence_id == id,
            User.deleted_at.is_(None)
        )
    )

    users = result.scalars().all()
    return [
        {
            "id": user.id,
            "role": user.role,
            "created_at": user.created_at
        }
        for user in users
    ]

@router.post("/{id}/users/{user_id}", status_code=201)
async def assign_user_to_residence(
    id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Assign a user to a residence"""
    # Check permissions
    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this residence")

    await get_residence_or_404(id, db)

    # Check if user exists
    user_result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already assigned
    existing = await db.execute(
        select(UserResidence).where(
            UserResidence.user_id == user_id,
            UserResidence.residence_id == id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already assigned to this residence")

    # Set user context for triggers
    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    assignment = UserResidence(user_id=user_id, residence_id=id)
    db.add(assignment)
    await db.commit()

@router.delete("/{id}/users/{user_id}", status_code=204)
async def remove_user_from_residence(
    id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Remove a user from a residence"""
    # Check permissions
    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this residence")

    await get_residence_or_404(id, db)

    # Set user context for triggers
    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    result = await db.execute(
        select(UserResidence).where(
            UserResidence.user_id == user_id,
            UserResidence.residence_id == id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="User not assigned to this residence")

    await db.delete(assignment)
    await db.commit()
