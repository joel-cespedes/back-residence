from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_db, get_current_user
from app.models import Resident, Bed, Residence, User, UserResidence
from app.schemas import (
    ResidentCreate, ResidentUpdate, ResidentOut, ResidentChangeBed,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid

router = APIRouter(prefix="/residents", tags=["residents"])

# -------------------- Helper Functions --------------------

async def apply_residence_context(db: AsyncSession, current: dict, residence_id: str | None):
    """Apply residence context for RLS"""
    if residence_id:
        if current["role"] != "superadmin":
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

async def get_resident_or_404(resident_id: str, db: AsyncSession) -> Resident:
    """Get resident by ID or raise 404"""
    result = await db.execute(
        select(Resident).where(Resident.id == resident_id, Resident.deleted_at.is_(None))
    )
    resident = result.scalar_one_or_none()
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    return resident

async def paginate_query_residents(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse:
    """Apply pagination and filters to a residents query"""

    if filter_params:
        if filter_params.date_from:
            query = query.where(Resident.created_at >= filter_params.date_from)
        if filter_params.date_to:
            query = query.where(Resident.created_at <= filter_params.date_to)
        if filter_params.status:
            query = query.where(Resident.status == filter_params.status)
        if filter_params.search:
            search_term = f"%{filter_params.search}%"
            query = query.where(or_(
                Resident.full_name.ilike(search_term),
                Resident.comments.ilike(search_term)
            ))

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    if pagination.sort_by:
        sort_field = getattr(Resident, pagination.sort_by, Resident.created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(Resident.created_at.desc())

    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)

    result = await db.execute(query)
    items = [dict(row._mapping) for row in result.scalars().all()]

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

@router.post("/", response_model=ResidentOut, status_code=201)
async def create_resident(
    data: ResidentCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="X-Residence-Id"),
):
    """Create a new resident"""
    await apply_residence_context(db, current, residence_id)

    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")

    if data.bed_id:
        bed_result = await db.execute(
            select(Bed).where(Bed.id == data.bed_id, Bed.deleted_at.is_(None))
        )
        bed = bed_result.scalar_one_or_none()
        if not bed:
            raise HTTPException(status_code=404, detail="Bed not found")
        if bed.residence_id != residence_id:
            raise HTTPException(status_code=400, detail="Bed must belong to the specified residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    resident = Resident(
        id=new_uuid(),
        residence_id=residence_id,
        **data.model_dump()
    )

    db.add(resident)
    await db.commit()
    await db.refresh(resident)
    return resident

@router.get("/", response_model=PaginatedResponse)
async def list_residents(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="X-Residence-Id"),
):
    """List residents with pagination and filters"""
    await apply_residence_context(db, current, residence_id)

    if current["role"] == "superadmin":
        if residence_id:
            query = select(Resident).where(Resident.residence_id == residence_id, Resident.deleted_at.is_(None))
        else:
            query = select(Resident).where(Resident.deleted_at.is_(None))
    else:
        if not residence_id:
            raise HTTPException(status_code=400, detail="Residence ID is required")
        query = select(Resident).where(Resident.residence_id == residence_id, Resident.deleted_at.is_(None))

    return await paginate_query_residents(query, db, pagination, filters)

@router.get("/{id}", response_model=ResidentOut)
async def get_resident(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get a specific resident"""
    resident = await get_resident_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == resident.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this resident")

    return resident

@router.put("/{id}", response_model=ResidentOut)
async def update_resident(
    id: str,
    data: ResidentUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a resident"""
    resident = await get_resident_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == resident.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this resident")

    if data.bed_id:
        bed_result = await db.execute(
            select(Bed).where(Bed.id == data.bed_id, Bed.deleted_at.is_(None))
        )
        bed = bed_result.scalar_one_or_none()
        if not bed:
            raise HTTPException(status_code=404, detail="Bed not found")
        if bed.residence_id != resident.residence_id:
            raise HTTPException(status_code=400, detail="Bed must belong to the same residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(resident, field, value)

    await db.commit()
    await db.refresh(resident)
    return resident

@router.delete("/{id}", status_code=204)
async def delete_resident(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Soft delete a resident"""
    resident = await get_resident_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == resident.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this resident")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    resident.deleted_at = func.now()
    await db.commit()

# -------------------- Additional Endpoints --------------------

@router.patch("/{resident_id}/bed", response_model=ResidentOut)
async def change_bed(
    resident_id: str,
    payload: ResidentChangeBed,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Change resident's bed assignment"""
    resident = await get_resident_or_404(resident_id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == resident.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this resident")

    if payload.new_bed_id:
        bed_result = await db.execute(
            select(Bed).where(Bed.id == payload.new_bed_id, Bed.deleted_at.is_(None))
        )
        bed = bed_result.scalar_one_or_none()
        if not bed:
            raise HTTPException(status_code=404, detail="Bed not found")
        if bed.residence_id != resident.residence_id:
            raise HTTPException(status_code=400, detail="Bed must belong to the same residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    resident.bed_id = payload.new_bed_id
    if payload.changed_at:
        resident.bed_changed_at = payload.changed_at
    else:
        from datetime import datetime
        resident.bed_changed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(resident)
    return resident

@router.get("/{id}/history", response_model=list[dict])
async def get_resident_history(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get resident history"""
    resident = await get_resident_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == resident.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this resident")

    result = await db.execute(
        text("""
            SELECT h.*
            FROM resident_history h
            WHERE h.resident_id = :resident_id
            ORDER BY h.valid_from DESC
        """),
        {"resident_id": id}
    )

    return [dict(row._mapping) for row in result.fetchall()]


