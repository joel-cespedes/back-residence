from __future__ import annotations

from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_db, get_current_user
from app.models import Floor, Room, Bed, Residence, User, UserResidence, Resident
from app.schemas import (
    FloorCreate, FloorUpdate, FloorOut,
    RoomCreate, RoomUpdate, RoomOut,
    BedCreate, BedUpdate, BedOut,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/structure", tags=["structure"])

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

async def get_residence_or_404(residence_id: str, db: AsyncSession) -> Residence:
    """Get residence by ID or raise 404"""
    result = await db.execute(
        select(Residence).where(Residence.id == residence_id, Residence.deleted_at.is_(None))
    )
    residence = result.scalar_one_or_none()
    if not residence:
        raise HTTPException(status_code=404, detail="Residence not found")
    return residence

async def get_floor_or_404(floor_id: str, db: AsyncSession, current: dict | None = None) -> Floor:
    if current:
        await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current['id']})

    async def fetch() -> Floor | None:
        result = await db.execute(
            select(Floor).where(Floor.id == floor_id, Floor.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    if current and current.get('role') != 'superadmin':
        accessible = await PermissionService.get_accessible_residence_ids(db, current['id'], current['role'])
        for residence_id in accessible:
            await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": residence_id})
            floor = await fetch()
            if floor:
                return floor
        raise HTTPException(status_code=404, detail='Floor not found')

    floor = await fetch()
    if not floor:
        raise HTTPException(status_code=404, detail='Floor not found')

    if current:
        await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": floor.residence_id})

    return floor

async def get_room_or_404(room_id: str, db: AsyncSession) -> Room:
    """Get room by ID or raise 404"""
    result = await db.execute(
        select(Room).where(Room.id == room_id, Room.deleted_at.is_(None))
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

async def get_bed_or_404(bed_id: str, db: AsyncSession) -> Bed:
    """Get bed by ID or raise 404"""
    result = await db.execute(
        select(Bed).where(Bed.id == bed_id, Bed.deleted_at.is_(None))
    )
    bed = result.scalar_one_or_none()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    return bed

async def paginate_query_structure(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse:
    """Apply pagination and filters to a structure query"""

    if filter_params and filter_params.search:
        search_term = f"%{filter_params.search}%"
        if hasattr(query.column_descriptions[0]['type'], 'name'):
            query = query.where(query.column_descriptions[0]['type'].name.ilike(search_term))

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    if pagination.sort_by:
        sort_field = getattr(query.column_descriptions[0]['type'], pagination.sort_by, query.column_descriptions[0]['type'].created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(query.column_descriptions[0]['type'].created_at.desc())

    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)

    result = await db.execute(query)
    items = []
    for row in result.scalars().all():
        item = {
            'id': row.id,
            'residence_id': row.residence_id,
            'name': row.name,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }
        # Add specific fields for different structure types
        if hasattr(row, 'floor_id'):
            item['floor_id'] = row.floor_id
        if hasattr(row, 'room_id'):
            item['room_id'] = row.room_id
        items.append(item)

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

async def paginate_floors_query(query, db: AsyncSession, pagination: PaginationParams) -> PaginatedResponse:
    """Apply pagination to floors query with joins"""
    # Count only unique floor IDs to avoid duplication due to joins
    count_query = select(func.count(Floor.id.distinct())).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query)

    if pagination.sort_by:
        sort_field = getattr(Floor, pagination.sort_by, Floor.created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(Floor.created_at.desc())

    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)
    result = await db.execute(query)

    items = []
    for row in result.all():
        floor, residence_name = row
        item = {
            'id': floor.id,
            'residence_id': floor.residence_id,
            'name': floor.name,
            'residence_name': residence_name,
            'created_at': floor.created_at,
            'updated_at': floor.updated_at
        }
        items.append(item)

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

# -------------------- FLOOR CRUD --------------------

@router.post("/floors", response_model=FloorOut, status_code=201)
async def create_floor(
    data: FloorCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Create a new floor"""
    await apply_residence_context(db, current, residence_id)

    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")

    await get_residence_or_404(residence_id, db)

    existing = await db.scalar(
        select(Floor.id).where(
            Floor.residence_id == residence_id,
            Floor.name == data.name,
            Floor.deleted_at.is_(None)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Floor name already exists in this residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    floor = Floor(
        id=new_uuid(),
        residence_id=residence_id,
        name=data.name
    )

    db.add(floor)
    await db.commit()
    await db.refresh(floor)
    return floor

@router.get("/floors", response_model=PaginatedResponse[FloorOut])
async def list_floors(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
) -> PaginatedResponse[FloorOut]:
    """List floors with pagination"""
    final_residence_id = residence_id
    print(f"DEBUG: list_floors called with residence_id={final_residence_id}")

    # Always use joins for consistency and to include residence_name
    query = select(Floor, Residence.name.label("residence_name")).join(Residence, Floor.residence_id == Residence.id)

    # Apply residence filter based on user role
    if current["role"] == "superadmin":
        # Superadmin can see all floors or filter by specific residence
        if final_residence_id:
            query = query.where(Floor.residence_id == final_residence_id, Floor.deleted_at.is_(None))
        else:
            query = query.where(Floor.deleted_at.is_(None))
    else:
        # For managers and professionals, get their allowed residences
        user_residences_result = await db.execute(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"]
            )
        )
        allowed_residence_ids = [row[0] for row in user_residences_result.all()]

        if not allowed_residence_ids:
            raise HTTPException(status_code=403, detail="No residences assigned")

        # If specific residence is provided, check if user has access
        if final_residence_id:
            if final_residence_id not in allowed_residence_ids:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
            query = query.where(Floor.residence_id == final_residence_id, Floor.deleted_at.is_(None))
        else:
            # Otherwise filter by all allowed residences
            query = query.where(
                Floor.residence_id.in_(allowed_residence_ids),
                Floor.deleted_at.is_(None)
            )

    # Apply search filter
    search_term = pagination.search or (filters.search if filters else None)
    if search_term:
        search_pattern = f"%{search_term.lower().strip()}%"
        query = query.where(
            or_(
                Floor.name.ilike(search_pattern),
                Residence.name.ilike(search_pattern)
            )
        )

    return await paginate_floors_query(query, db, pagination)

@router.get("/floors/{residence_id}/simple")
async def floors_simple(residence_id: str, db: AsyncSession = Depends(get_db)):
    """Get simple list of floors for a residence (legacy endpoint)"""
    r = await db.execute(
        select(Floor, Residence.name.label("residence_name"))
        .join(Residence, Floor.residence_id == Residence.id)
        .where(Floor.residence_id == residence_id, Floor.deleted_at.is_(None))
    )
    return [
        {
            "id": f.id,
            "name": f.name,
            "residence_id": f.residence_id,
            "residence_name": residence_name,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None
        }
        for f, residence_name in r
    ]

@router.get("/floors/{id}", response_model=FloorOut)
async def get_floor(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get a specific floor"""
    floor = await get_floor_or_404(id, db, current)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == floor.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this floor")

    return floor

@router.put("/floors/{id}", response_model=FloorOut)
async def update_floor(
    id: str,
    data: FloorUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="residence_id"),
):
    """Update a floor"""
    await apply_residence_context(db, current, residence_id)
    floor = await get_floor_or_404(id, db, current)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == floor.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this floor")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    update_data = data.dict(exclude_unset=True)

    new_residence_id = update_data.pop('residence_id', None)
    if new_residence_id and new_residence_id != floor.residence_id:
        await get_residence_or_404(new_residence_id, db)

        if current['role'] != 'superadmin':
            check = await db.execute(
                select(UserResidence).where(
                    UserResidence.user_id == current['id'],
                    UserResidence.residence_id == new_residence_id,
                )
            )
            if check.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail='Access denied to this residence')

        floor.residence_id = new_residence_id

    for field, value in update_data.items():
        setattr(floor, field, value)

    await db.commit()
    await db.refresh(floor)
    return floor

@router.delete("/floors/{id}", status_code=204)
async def delete_floor(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="residence_id"),
):
    """Soft delete a floor"""
    await apply_residence_context(db, current, residence_id)
    floor = await get_floor_or_404(id, db, current)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == floor.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this floor")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    floor.deleted_at = func.now()
    await db.commit()

# -------------------- ROOM CRUD --------------------

async def paginate_query_rooms(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse:
    """Apply pagination and filters to a room query with joins"""
    if filter_params and filter_params.search:
        search_term = f"%{filter_params.search}%"
        query = query.where(Room.name.ilike(search_term))

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    if pagination.sort_by:
        sort_field = getattr(Room, pagination.sort_by, Room.created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(Room.created_at.desc())

    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)
    result = await db.execute(query)

    items = []
    for row in result.all():
        item = {
            'id': row.id,
            'residence_id': row.residence_id,
            'floor_id': row.floor_id,
            'name': row.name,
            'floor_name': row.floor_name or 'Desconocido',
            'residence_name': row.residence_name or 'Desconocida',
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }
        items.append(item)

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

@router.post("/rooms", response_model=RoomOut, status_code=201)
async def create_room(
    data: RoomCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Create a new room"""
    await apply_residence_context(db, current, residence_id)

    floor = await get_floor_or_404(data.floor_id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == floor.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this floor")

    existing = await db.scalar(
        select(Room.id).where(
            Room.floor_id == data.floor_id,
            Room.name == data.name,
            Room.deleted_at.is_(None)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Room name already exists on this floor")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    room = Room(
        id=new_uuid(),
        residence_id=floor.residence_id,
        floor_id=data.floor_id,
        name=data.name
    )

    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room

@router.get("/rooms", response_model=PaginatedResponse[RoomOut])
async def list_rooms(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    floor_id: str | None = Query(None, description="Filter by floor ID"),
    search: str | None = Query(None, description="Search term for room name, floor name, or residence name"),
) -> PaginatedResponse[RoomOut]:
    """List rooms with pagination"""
    print(f"DEBUG: list_rooms called with residence_id={residence_id}, floor_id={floor_id}")

    # Create query with joins to get related names
    query = select(
        Room.id,
        Room.name,
        Room.residence_id,
        Room.floor_id,
        Room.created_at,
        Room.updated_at,
        Floor.name.label('floor_name'),
        Residence.name.label('residence_name')
    ).join(
        Floor, Room.floor_id == Floor.id, isouter=True
    ).join(
        Residence, Room.residence_id == Residence.id, isouter=True
    ).where(
        Room.deleted_at.is_(None)
    )

    # Apply search filter if provided
    if search:
        search_term = f"%{search.lower().strip()}%"
        query = query.where(
            or_(
                Room.name.ilike(search_term),
                Floor.name.ilike(search_term),
                Residence.name.ilike(search_term)
            )
        )

    # Apply role-based filtering
    if current["role"] == "superadmin":
        # Superadmin can see all rooms or filter by specific residence/floor
        if residence_id:
            query = query.where(Room.residence_id == residence_id)
        if floor_id:
            query = query.where(Room.floor_id == floor_id)
    else:
        # For managers and professionals, get their allowed residences
        user_residences_result = await db.execute(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"]
            )
        )
        allowed_residence_ids = [row[0] for row in user_residences_result.all()]

        if not allowed_residence_ids:
            raise HTTPException(status_code=403, detail="No residences assigned")

        # If specific residence is provided, check if user has access
        if residence_id:
            if residence_id not in allowed_residence_ids:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
            query = query.where(Room.residence_id == residence_id)
        else:
            # Otherwise filter by all allowed residences
            query = query.where(Room.residence_id.in_(allowed_residence_ids))

        # Apply floor filter if provided
        if floor_id:
            query = query.where(Room.floor_id == floor_id)

    return await paginate_query_rooms(query, db, pagination, filters)

@router.get("/rooms/{floor_id}/simple")
async def rooms_simple(floor_id: str, db: AsyncSession = Depends(get_db)):
    """Get simple list of rooms for a floor (legacy endpoint)"""

    # First verify the floor exists
    floor_check = await db.execute(
        select(Floor).where(Floor.id == floor_id, Floor.deleted_at.is_(None))
    )
    floor = floor_check.scalar_one_or_none()

    if not floor:
        raise HTTPException(
            status_code=404,
            detail=f"Floor with ID {floor_id} not found"
        )

    # Then get rooms for that floor
    r = await db.execute(
        select(Room, Floor.name.label("floor_name"), Residence.name.label("residence_name"))
        .join(Floor, Room.floor_id == Floor.id)
        .join(Residence, Floor.residence_id == Residence.id)
        .where(Room.floor_id == floor_id, Room.deleted_at.is_(None))
    )
    return [
        {
            "id": x[0].id,
            "name": x[0].name,
            "floor_id": x[0].floor_id,
            "residence_id": x[0].residence_id,
            "floor_name": x[1],
            "residence_name": x[2],
            "created_at": x[0].created_at.isoformat() if x[0].created_at else None,
            "updated_at": x[0].updated_at.isoformat() if x[0].updated_at else None
        }
        for x in r.all()
    ]

@router.get("/rooms/{id}", response_model=RoomOut)
async def get_room(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get a specific room"""
    room = await get_room_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == room.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this room")

    return room

@router.put("/rooms/{id}", response_model=RoomOut)
async def update_room(
    id: str,
    data: RoomUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a room"""
    room = await get_room_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == room.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this room")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    update_data = data.dict(exclude_unset=True)
    
    # Si se va a cambiar el floor_id, validar que el nuevo piso existe y el usuario tenga acceso
    if 'floor_id' in update_data and update_data['floor_id'] != room.floor_id:
        new_floor = await get_floor_or_404(update_data['floor_id'], db)
        
        # Verificar que el usuario tenga acceso al nuevo piso
        if current["role"] != "superadmin":
            result = await db.execute(
                select(UserResidence).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.residence_id == new_floor.residence_id,
                )
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail="Access denied to the target floor")
        
        # Actualizar residence_id si el piso pertenece a otra residencia
        room.residence_id = new_floor.residence_id
    
    for field, value in update_data.items():
        setattr(room, field, value)

    await db.commit()
    await db.refresh(room)
    return room

@router.delete("/rooms/{id}", status_code=204)
async def delete_room(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Soft delete a room"""
    room = await get_room_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == room.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this room")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    room.deleted_at = func.now()
    await db.commit()

# -------------------- BED CRUD --------------------

@router.post("/beds", response_model=BedOut, status_code=201)
async def create_bed(
    data: BedCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Create a new bed"""
    await apply_residence_context(db, current, residence_id)

    room = await get_room_or_404(data.room_id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == room.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this room")

    existing = await db.scalar(
        select(Bed.id).where(
            Bed.room_id == data.room_id,
            Bed.name == data.name,
            Bed.deleted_at.is_(None)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Bed name already exists in this room")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    bed = Bed(
        id=new_uuid(),
        residence_id=room.residence_id,
        room_id=data.room_id,
        name=data.name
    )

    db.add(bed)
    await db.commit()
    await db.refresh(bed)
    return bed

@router.get("/beds", response_model=PaginatedResponse[BedOut])
async def list_beds(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    floor_id: str | None = Query(None, description="Filter by floor ID"),
) -> PaginatedResponse[BedOut]:
    """List beds with pagination and related names"""
    final_residence_id = residence_id
    print(f"DEBUG: list_beds called with residence_id={final_residence_id}, floor_id={floor_id}")

    # Build query with joins to get related names
    base_query = select(
        Bed,
        Room.name.label("room_name"),
        Floor.name.label("floor_name"),
        Residence.name.label("residence_name"),
        Resident.full_name.label("resident_name")
    ).join(Room, Bed.room_id == Room.id, isouter=True)\
     .join(Floor, Room.floor_id == Floor.id, isouter=True)\
     .join(Residence, Floor.residence_id == Residence.id, isouter=True)\
     .join(Resident, Bed.id == Resident.bed_id, isouter=True)\
     .where(Bed.deleted_at.is_(None))

    # Apply filters based on user role and provided parameters
    if current["role"] == "superadmin":
        # Superadmin can see all beds or filter by specific residence/floor
        if final_residence_id:
            base_query = base_query.where(Bed.residence_id == final_residence_id)
        if floor_id:
            base_query = base_query.where(Floor.id == floor_id)
    else:
        # For managers and professionals, get their allowed residences
        user_residences_result = await db.execute(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"]
            )
        )
        allowed_residence_ids = [row[0] for row in user_residences_result.all()]

        if not allowed_residence_ids:
            raise HTTPException(status_code=403, detail="No residences assigned")

        # If specific residence is provided, check if user has access
        if final_residence_id:
            if final_residence_id not in allowed_residence_ids:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
            base_query = base_query.where(Bed.residence_id == final_residence_id)
        else:
            # Otherwise filter by all allowed residences
            base_query = base_query.where(Bed.residence_id.in_(allowed_residence_ids))

        # Apply floor filter if provided
        if floor_id:
            base_query = base_query.where(Floor.id == floor_id)

    # Apply search filter if provided
    if filters and filters.search:
        search_term = f"%{filters.search}%"
        base_query = base_query.where(Bed.name.ilike(search_term))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    if pagination.sort_by:
        sort_field = getattr(Bed, pagination.sort_by, Bed.created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        base_query = base_query.order_by(sort_field)

    offset = (pagination.page - 1) * pagination.size
    base_query = base_query.offset(offset).limit(pagination.size)

    # Execute query
    result = await db.execute(base_query)
    items = []

    for row in result.all():
        bed, room_name, floor_name, residence_name, resident_name = row
        items.append({
            "id": bed.id,
            "name": bed.name,
            "room_id": bed.room_id,
            "residence_id": bed.residence_id,
            "room_name": room_name or "Desconocida",
            "floor_name": floor_name or "Desconocido",
            "residence_name": residence_name or "Desconocida",
            "resident_name": resident_name or "Sin asignar",
            "created_at": bed.created_at.isoformat() if bed.created_at else None,
            "updated_at": bed.updated_at.isoformat() if bed.updated_at else None
        })

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

@router.get("/beds/{room_id}/simple")
async def beds_simple(room_id: str, db: AsyncSession = Depends(get_db)):
    """Get simple list of beds for a room (legacy endpoint)"""
    r = await db.execute(
        select(Bed, Room.name.label("room_name"), Floor.name.label("floor_name"), Residence.name.label("residence_name"), Residence.id.label("residence_id"))
        .join(Room, Bed.room_id == Room.id)
        .join(Floor, Room.floor_id == Floor.id)
        .join(Residence, Floor.residence_id == Residence.id)
        .where(Bed.room_id == room_id, Bed.deleted_at.is_(None))
    )
    return [
        {
            "id": x[0].id,
            "name": x[0].name,
            "room_id": x[0].room_id,
            "residence_id": x[4],
            "room_name": x[1],
            "floor_name": x[2],
            "residence_name": x[3],
            "created_at": x[0].created_at.isoformat() if x[0].created_at else None,
            "updated_at": x[0].updated_at.isoformat() if x[0].updated_at else None
        }
        for x in r.all()
    ]

@router.get("/beds/{id}", response_model=BedOut)
async def get_bed(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get a specific bed"""
    bed = await get_bed_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == bed.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this bed")

    return bed

@router.get("/beds/{id}/details")
async def bed_details(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get detailed bed information"""
    bed = await get_bed_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == bed.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this bed")

    r = await db.execute(
        select(Bed, Room.name.label("room_name"), Floor.name.label("floor_name"), Residence.name.label("residence_name"))
        .join(Room, Bed.room_id == Room.id)
        .join(Floor, Room.floor_id == Floor.id)
        .join(Residence, Floor.residence_id == Residence.id)
        .where(Bed.id == id, Bed.deleted_at.is_(None))
    )
    result = r.first()
    if not result:
        raise HTTPException(status_code=404, detail="Bed not found")

    bed_data, room_name, floor_name, residence_name = result
    return {
        "id": bed_data.id,
        "name": bed_data.name,
        "room_id": bed_data.room_id,
        "residence_id": bed_data.residence_id,
        "room_name": room_name,
        "floor_name": floor_name,
        "residence_name": residence_name,
        "created_at": bed_data.created_at.isoformat() if bed_data.created_at else None,
        "updated_at": bed_data.updated_at.isoformat() if bed_data.updated_at else None
    }

@router.put("/beds/{id}", response_model=BedOut)
async def update_bed(
    id: str,
    data: BedUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a bed"""
    bed = await get_bed_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == bed.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this bed")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bed, field, value)

    await db.commit()
    await db.refresh(bed)
    return bed

@router.delete("/beds/{id}", status_code=204)
async def delete_bed(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Soft delete a bed"""
    bed = await get_bed_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == bed.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this bed")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    bed.deleted_at = func.now()
    await db.commit()



