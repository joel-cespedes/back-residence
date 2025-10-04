from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_db, get_current_user
from app.models import Tag, ResidentTag, Residence, User, UserResidence, Resident
from app.schemas import (
    TagCreate, TagUpdate, TagOut, ResidentTagAssign,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid

router = APIRouter(prefix="/tags", tags=["tags"])

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

async def get_tag_or_404(tag_id: str, db: AsyncSession) -> Tag:
    """Get tag by ID or raise 404"""
    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.deleted_at.is_(None))
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag

async def paginate_query_tags(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse:
    """Apply pagination and filters to a tags query"""

    if filter_params and filter_params.search:
        search_term = f"%{filter_params.search}%"
        query = query.where(Tag.name.ilike(search_term))

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    if pagination.sort_by:
        sort_field = getattr(Tag, pagination.sort_by, Tag.created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(Tag.created_at.desc())

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

@router.post("/", response_model=TagOut, status_code=201)
async def create_tag(
    data: TagCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="residence_id"),
):
    """Create a new tag"""
    await apply_residence_context(db, current, residence_id)

    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")

    existing = await db.scalar(
        select(Tag.id).where(
            Tag.residence_id == residence_id,
            Tag.name == data.name,
            Tag.deleted_at.is_(None)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Tag name already exists in this residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    tag = Tag(
        id=new_uuid(),
        residence_id=residence_id,
        name=data.name
    )

    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag

@router.get("/", response_model=PaginatedResponse[TagOut])
async def list_tags(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="residence_id"),
) -> PaginatedResponse[TagOut]:
    """List tags with pagination and filters"""
    await apply_residence_context(db, current, residence_id)

    if current["role"] == "superadmin":
        if residence_id:
            query = select(Tag).where(Tag.residence_id == residence_id, Tag.deleted_at.is_(None))
        else:
            query = select(Tag).where(Tag.deleted_at.is_(None))
    else:
        if not residence_id:
            raise HTTPException(status_code=400, detail="Residence ID is required")
        query = select(Tag).where(Tag.residence_id == residence_id, Tag.deleted_at.is_(None))

    return await paginate_query_tags(query, db, pagination, filters)

@router.get("/simple", response_model=list[dict])
async def list_tags_simple(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="residence_id"),
):
    """Legacy endpoint: List tags without pagination"""
    await apply_residence_context(db, current, residence_id)

    if current["role"] == "superadmin":
        if residence_id:
            r = await db.execute(select(Tag).where(Tag.residence_id == residence_id, Tag.deleted_at.is_(None)))
        else:
            r = await db.execute(select(Tag).where(Tag.deleted_at.is_(None)))
    else:
        if not residence_id:
            raise HTTPException(status_code=400, detail="Residence ID is required")
        r = await db.execute(select(Tag).where(Tag.residence_id == residence_id, Tag.deleted_at.is_(None)))

    return [{"id": t.id, "name": t.name} for t in r.scalars().all()]

@router.get("/{id}", response_model=TagOut)
async def get_tag(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get a specific tag"""
    tag = await get_tag_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == tag.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this tag")

    return tag

@router.put("/{id}", response_model=TagOut)
async def update_tag(
    id: str,
    data: TagUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a tag"""
    tag = await get_tag_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == tag.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this tag")

    if data.name and data.name != tag.name:
        existing = await db.scalar(
            select(Tag.id).where(
                Tag.residence_id == tag.residence_id,
                Tag.name == data.name,
                Tag.id != id,
                Tag.deleted_at.is_(None)
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Tag name already exists in this residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tag, field, value)

    await db.commit()
    await db.refresh(tag)
    return tag

@router.delete("/{id}", status_code=204)
async def delete_tag(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Soft delete a tag"""
    tag = await get_tag_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == tag.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this tag")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    tag.deleted_at = func.now()
    await db.commit()

# -------------------- Assignment Endpoints --------------------

@router.post("/{tag_id}/residents/{resident_id}", response_model=dict, status_code=201)
async def assign_tag_to_resident(
    tag_id: str,
    resident_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Assign a tag to a resident"""
    tag = await get_tag_or_404(tag_id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == tag.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this tag")

    resident_result = await db.execute(
        select(Resident).where(Resident.id == resident_id, Resident.deleted_at.is_(None))
    )
    resident = resident_result.scalar_one_or_none()
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    if resident.residence_id != tag.residence_id:
        raise HTTPException(status_code=400, detail="Resident must belong to the same residence as the tag")

    existing = await db.scalar(
        select(ResidentTag).where(
            ResidentTag.resident_id == resident_id,
            ResidentTag.tag_id == tag_id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Tag already assigned to this resident")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    assignment = ResidentTag(resident_id=resident_id, tag_id=tag_id)
    db.add(assignment)
    await db.commit()

@router.delete("/{tag_id}/residents/{resident_id}", status_code=204)
async def remove_tag_from_resident(
    tag_id: str,
    resident_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Remove a tag from a resident"""
    tag = await get_tag_or_404(tag_id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == tag.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this tag")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    result = await db.execute(
        select(ResidentTag).where(
            ResidentTag.resident_id == resident_id,
            ResidentTag.tag_id == tag_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Tag not assigned to this resident")

    await db.delete(assignment)
    await db.commit()

@router.get("/{tag_id}/residents", response_model=list[dict])
async def get_tag_residents(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get residents assigned to a tag"""
    tag = await get_tag_or_404(tag_id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == tag.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this tag")

    result = await db.execute(
        select(Resident)
        .join(ResidentTag, ResidentTag.resident_id == Resident.id)
        .where(
            ResidentTag.tag_id == tag_id,
            Resident.deleted_at.is_(None)
        )
    )

    residents = result.scalars().all()
    return [
        {
            "id": resident.id,
            "full_name": resident.full_name,
            "status": resident.status,
            "created_at": resident.created_at
        }
        for resident in residents
    ]



