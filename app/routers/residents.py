from __future__ import annotations

from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_db, get_current_user
from app.models import Resident, Bed, Residence, User, UserResidence, Room, Floor
from app.schemas import (
    ResidentCreate, ResidentUpdate, ResidentOut, ResidentChangeBed,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/residents", tags=["residents"])

# -------------------- Helper Functions --------------------

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
    filter_params: FilterParams = None,
    floor_id: str = None,
    room_id: str = None,
    bed_id: str = None,
    residence_id: str = None
) -> PaginatedResponse[ResidentOut]:
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

    # Apply structure filters - apply all filters
    if residence_id:
        query = query.where(Resident.residence_id == residence_id)
    if floor_id:
        query = query.where(Floor.id == floor_id)
    if room_id:
        query = query.where(Room.id == room_id)
    if bed_id:
        query = query.where(Resident.bed_id == bed_id)

    # Apply filters to count query as well
    count_query = select(func.count(Resident.id)).select_from(Resident)

    if filter_params:
        if filter_params.date_from:
            count_query = count_query.where(Resident.created_at >= filter_params.date_from)
        if filter_params.date_to:
            count_query = count_query.where(Resident.created_at <= filter_params.date_to)
        if filter_params.status:
            count_query = count_query.where(Resident.status == filter_params.status)
        if filter_params.search:
            search_term = f"%{filter_params.search}%"
            count_query = count_query.where(or_(
                Resident.full_name.ilike(search_term),
                Resident.comments.ilike(search_term)
            ))

    # Apply structure filters to count query as well - simplify to avoid duplicate joins
    if residence_id:
        count_query = count_query.where(Resident.residence_id == residence_id)
    if floor_id:
        count_query = count_query.join(Bed, Resident.bed_id == Bed.id, isouter=True).join(Room, Bed.room_id == Room.id, isouter=True).join(Floor, Room.floor_id == Floor.id, isouter=True).where(Floor.id == floor_id)
    elif room_id:
        count_query = count_query.join(Bed, Resident.bed_id == Bed.id, isouter=True).join(Room, Bed.room_id == Room.id, isouter=True).where(Room.id == room_id)
    elif bed_id:
        count_query = count_query.where(Resident.bed_id == bed_id)

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
    items = []
    for row in result.all():
        # Row structure: [Resident, bed_name, room_name, floor_name, residence_name]
        resident = row[0]
        item_dict = {}

        # Add all Resident columns
        for column in resident.__table__.columns.keys():
            item_dict[column] = getattr(resident, column)

        # Add relationship names
        item_dict['bed_name'] = row[1]
        item_dict['room_name'] = row[2]
        item_dict['floor_name'] = row[3]
        item_dict['residence_name'] = row[4]

        items.append(item_dict)

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
):
    """Create a new resident"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Validate that user has permission to create residents
        if not PermissionService.can_create_resident(current["role"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permiso para crear residentes"
            )

        # Validate access to the specified residence
        await PermissionService.validate_residence_access(
            db, current["id"], data.residence_id, current["role"]
        )

        if not data.residence_id:
            raise HTTPException(status_code=400, detail="Residence ID is required")

        # Validar cama y obtener room_id y floor_id
        room_id = None
        floor_id = None
        if data.bed_id:
            bed_result = await db.execute(
                select(Bed, Room.floor_id).join(Room, Bed.room_id == Room.id)
                .where(Bed.id == data.bed_id, Bed.deleted_at.is_(None))
            )
            result_row = bed_result.first()
            if not result_row:
                raise HTTPException(status_code=404, detail="Bed not found")
                
            bed, floor_id = result_row
            room_id = bed.room_id
            
            if bed.residence_id != data.residence_id:
                raise HTTPException(status_code=400, detail="Bed must belong to the specified residence")

        await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

        logger.error(f"Creating resident with data: {data.model_dump()}")

        # Create resident data excluding residence_id from model_dump to avoid duplicate argument
        resident_data = data.model_dump()
        resident_data.pop('residence_id', None)  # Remove residence_id to avoid duplicate

        resident = Resident(
            id=new_uuid(),
            residence_id=data.residence_id,
            room_id=room_id,    # Asignar room_id
            floor_id=floor_id,  # Asignar floor_id
            **resident_data
        )

        db.add(resident)
        await db.commit()
        await db.refresh(resident)
        return resident
    except Exception as e:
        logger.error(f"Error in create_resident: {str(e)}")
        logger.error(f"Data received: {data.model_dump() if hasattr(data, 'model_dump') else data}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/", response_model=PaginatedResponse[ResidentOut])
async def list_residents(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    floor_id: str | None = Query(None),
    room_id: str | None = Query(None),
    bed_id: str | None = Query(None),
    residence_id_param: str | None = Query(None, alias="residence_id"),
) -> PaginatedResponse[ResidentOut]:
    """List residents with pagination and filters - filtered by user role and assignments"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Build base query with SUPER optimized joins - relaciones directas
        base_query = select(
            Resident,
            Bed.name.label("bed_name"),
            Room.name.label("room_name"),
            Floor.name.label("floor_name"),
            Residence.name.label("residence_name")
        ).join(Residence, Resident.residence_id == Residence.id
        ).join(Bed, Resident.bed_id == Bed.id, isouter=True
        ).join(Room, Resident.room_id == Room.id, isouter=True  # ← DIRECTO desde resident
        ).join(Floor, Resident.floor_id == Floor.id, isouter=True  # ← DIRECTO desde resident
        ).where(Resident.deleted_at.is_(None))

        # Apply filtering based on user role and assignments
        base_query = await PermissionService.filter_query_by_residence(
            base_query, db, current["id"], current["role"], residence_id_param
        )

        logger.error(f"Base query before pagination: {base_query}")

        result = await paginate_query_residents(base_query, db, pagination, filters, floor_id, room_id, bed_id, residence_id_param)
        logger.error(f"Result items count: {len(result.items) if hasattr(result, 'items') else 0}")
        return result
    except Exception as e:
        logger.error(f"Error in list_residents: {str(e)}")
        logger.error(f"Params: floor_id={floor_id}, room_id={room_id}, bed_id={bed_id}, residence_id={residence_id_param}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{id}", response_model=dict)
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

    # Get resident with relationship data - OPTIMIZADO con relaciones directas
    result = await db.execute(
        select(
            Resident,
            Bed.name.label("bed_name"),
            Room.name.label("room_name"), 
            Floor.name.label("floor_name"),
            Residence.name.label("residence_name")
        ).join(Residence, Resident.residence_id == Residence.id
        ).join(Bed, Resident.bed_id == Bed.id, isouter=True
        ).join(Room, Resident.room_id == Room.id, isouter=True  # ← DIRECTO, no a través de bed
        ).join(Floor, Resident.floor_id == Floor.id, isouter=True  # ← DIRECTO, no a través de room
        ).where(Resident.id == id)
    )

    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Resident not found")

    # Build response dictionary
    resident_data = row[0]
    response_dict = {}

    # Add all Resident columns (ahora incluye room_id y floor_id)
    for column in resident_data.__table__.columns.keys():
        response_dict[column] = getattr(resident_data, column)

    # Add relationship names
    response_dict['bed_name'] = row[1]
    response_dict['room_name'] = row[2]
    response_dict['floor_name'] = row[3]
    response_dict['residence_name'] = row[4]

    return response_dict

@router.put("/{id}", response_model=ResidentOut)
async def update_resident(
    id: str,
    data: ResidentUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a resident"""
    import logging
    logger = logging.getLogger(__name__)

    print(f"PUT - Starting update for resident ID: {id}")
    print(f"PUT - Data received: {data}")

    resident = await get_resident_or_404(id, db)
    print(f"PUT - Resident found: {resident.residence_id}")

    # Validate access to resident's residence
    await PermissionService.validate_residence_access(
        db, current["id"], resident.residence_id, current["role"]
    )

    # Si se está actualizando bed_id, también actualizar room_id y floor_id
    if data.bed_id:
        bed_result = await db.execute(
            select(Bed, Room.floor_id).join(Room, Bed.room_id == Room.id)
            .where(Bed.id == data.bed_id, Bed.deleted_at.is_(None))
        )
        result_row = bed_result.first()
        if not result_row:
            raise HTTPException(status_code=404, detail="Bed not found")
            
        bed, floor_id = result_row

        # Log para depuración
        print(f"PUT - Bed residence_id: {bed.residence_id}")
        print(f"PUT - Resident residence_id: {resident.residence_id}")
        print(f"PUT - Data residence_id: {data.residence_id}")

        if bed.residence_id != resident.residence_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "cross_residence_bed_assignment",
                    "message": "No puedes asignar una cama de una residencia diferente",
                    "steps_required": [
                        "1. Primero quita la cama actual (deja bed_id vacío)",
                        "2. Luego actualiza la residencia si es necesario",
                        "3. Finalmente asigna la nueva cama"
                    ],
                    "current_resident_residence": resident.residence_id,
                    "target_bed_residence": bed.residence_id
                }
            )

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    # Actualizar campos normales (excluyendo bed_id, room_id, floor_id que se manejan especialmente)
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field not in ['bed_id', 'room_id', 'floor_id']:  # Estos se manejan por separado
            setattr(resident, field, value)
    
    # Manejo especial de bed_id, room_id y floor_id
    if data.bed_id:
        # Si se asigna una cama, actualizar todos los niveles jerárquicos
        resident.bed_id = data.bed_id
        resident.room_id = bed.room_id
        resident.floor_id = floor_id
    elif 'bed_id' in update_data and data.bed_id is None:
        # Si explícitamente se quita la cama, solo quitarla
        resident.bed_id = None
        # Mantener room_id y floor_id si se proporcionaron explícitamente
        if 'room_id' in update_data:
            resident.room_id = data.room_id
        else:
            resident.room_id = None
        if 'floor_id' in update_data:
            resident.floor_id = data.floor_id
        else:
            resident.floor_id = None
    else:
        # Si no se toca bed_id, actualizar room_id y floor_id independientemente si se proporcionaron
        if 'room_id' in update_data:
            resident.room_id = data.room_id
        if 'floor_id' in update_data:
            resident.floor_id = data.floor_id

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
        # Obtener la cama con su información de room y floor
        bed_result = await db.execute(
            select(Bed, Room.floor_id).join(Room, Bed.room_id == Room.id)
            .where(Bed.id == payload.new_bed_id, Bed.deleted_at.is_(None))
        )
        result_row = bed_result.first()
        if not result_row:
            raise HTTPException(status_code=404, detail="Bed not found")
        
        bed, floor_id = result_row
        if bed.residence_id != resident.residence_id:
            raise HTTPException(status_code=400, detail="Bed must belong to the same residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    # Actualizar bed_id, room_id y floor_id de manera consistente
    if payload.new_bed_id:
        resident.bed_id = payload.new_bed_id
        resident.room_id = bed.room_id  # Actualizar room_id
        resident.floor_id = floor_id    # Actualizar floor_id
    else:
        # Si se quita la asignación de cama
        resident.bed_id = None
        resident.room_id = None
        resident.floor_id = None
        
    if payload.changed_at:
        resident.status_changed_at = payload.changed_at  # Corregir nombre del campo
    else:
        from datetime import datetime, timezone
        resident.status_changed_at = datetime.now(timezone.utc)

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

    return [dict(row) for row in result.fetchall()]


