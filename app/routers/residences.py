# app/routers/residences.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_db, get_current_user
from app.models import Residence, User, UserResidence
from app.schemas import (
    ResidenceCreate, ResidenceUpdate, ResidenceOut,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid, decrypt_data, encrypt_data
from sqlalchemy import text

router = APIRouter(prefix="/residences", tags=["residences"])

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