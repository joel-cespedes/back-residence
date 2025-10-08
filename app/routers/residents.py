from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, aliased

from app.deps import get_db, get_current_user
from app.models import (
    Resident, Bed, Residence, User, UserResidence, Room, Floor, Device,
    Measurement, TaskApplication, ResidentHistory, TaskTemplate, TaskCategory
)
from app.schemas import (
    ResidentCreate, ResidentUpdate, ResidentOut, ResidentChangeBed,
    PaginationParams, PaginatedResponse, FilterParams,
    ResidentChronologyResponse, MeasurementEvent, TaskEvent,
    BedChangeEvent, StatusChangeEvent
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

async def apply_residence_context_or_infer(
    db: AsyncSession,
    current: dict,
    residence_id: str | None,
    resident_id: str | None = None,
    device_id: str | None = None,
) -> str:
    """
    Devuelve residence_id efectivo:
      - usa el header si viene (validando pertenencia),
      - si no, intenta inferirlo por resident_id o device_id,
      - si no se puede y no es superadmin -> 428.
    Fija app.residence_id en la sesión para RLS/consultas posteriores.
    """
    rid = residence_id

    # Inferir por residente
    if not rid and resident_id:
        rid = await db.scalar(
            select(Resident.residence_id).where(
                Resident.id == resident_id,
                Resident.deleted_at.is_(None)
            )
        )
        if not rid:
            raise HTTPException(status_code=400, detail="Resident not found")

    # Inferir por dispositivo
    if not rid and device_id:
        rid = await db.scalar(
            select(Device.residence_id).where(
                Device.id == device_id,
                Device.deleted_at.is_(None)
            )
        )
        if not rid:
            raise HTTPException(status_code=400, detail="Device not found")

    if not rid and current["role"] != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Select a residence (send residence_id or include resident_id/device_id to infer)"
        )

    # Validar pertenencia (salvo superadmin)
    if rid and current["role"] != "superadmin":
        ok = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == rid,
            )
        )
        if ok.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Residence not allowed for this user")

    # Fijar contexto
    if rid:
        await db.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": rid})

    return rid

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

        # Create resident data excluding duplicates from model_dump
        resident_data = data.model_dump()
        resident_data.pop('residence_id', None)
        resident_data.pop('room_id', None)    # Remove to avoid duplicate with calculated value
        resident_data.pop('floor_id', None)   # Remove to avoid duplicate with calculated value

        resident = Resident(
            id=new_uuid(),
            residence_id=data.residence_id,
            room_id=room_id,    # Use calculated room_id from bed
            floor_id=floor_id,  # Use calculated floor_id from bed
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

        result = await paginate_query_residents(base_query, db, pagination, filters, floor_id, room_id, bed_id, residence_id_param)
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


@router.get("/{id}/chronology", response_model=ResidentChronologyResponse)
async def get_resident_chronology(
    id: str,
    include_measurements: bool = Query(True, description="Incluir mediciones"),
    include_tasks: bool = Query(True, description="Incluir tareas"),
    include_bed_changes: bool = Query(True, description="Incluir cambios de cama"),
    include_status_changes: bool = Query(True, description="Incluir cambios de estado"),
    date_from: Optional[datetime] = Query(None, description="Fecha desde"),
    date_to: Optional[datetime] = Query(None, description="Fecha hasta"),
    limit: int = Query(10, ge=1, le=100, description="Límite de eventos"),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID")
):
    """
    Obtiene la cronología completa de un residente: mediciones, tareas y cambios de cama/estado.
    Los eventos se retornan ordenados por fecha descendente (más recientes primero).
    """
    # Verificar que el residente existe
    resident_query = select(Resident).where(Resident.id == id, Resident.deleted_at.is_(None))
    result = await db.execute(resident_query)
    resident = result.scalar_one_or_none()

    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    # Validar acceso a la residencia
    rid = await apply_residence_context_or_infer(db, current, residence_id, resident_id=id)

    events = []

    # 1. MEDICIONES
    if include_measurements:
        measurement_query = select(
            Measurement,
            User.name.label("recorded_by_name"),
            Device.name.label("device_name")
        ).join(
            User, Measurement.recorded_by == User.id, isouter=True
        ).join(
            Device, Measurement.device_id == Device.id, isouter=True
        ).where(
            Measurement.resident_id == id,
            Measurement.deleted_at.is_(None)
        )

        if date_from:
            measurement_query = measurement_query.where(Measurement.taken_at >= date_from)
        if date_to:
            measurement_query = measurement_query.where(Measurement.taken_at <= date_to)

        measurement_result = await db.execute(measurement_query)

        for measurement, recorded_by_name, device_name in measurement_result.all():
            # Construir valores según el tipo
            values = {}
            if measurement.type == "bp":
                values = {
                    "systolic": measurement.systolic,
                    "diastolic": measurement.diastolic,
                    "pulse_bpm": measurement.pulse_bpm
                }
            elif measurement.type == "spo2":
                values = {
                    "spo2": measurement.spo2,
                    "pulse_bpm": measurement.pulse_bpm
                }
            elif measurement.type == "weight":
                values = {"weight_kg": measurement.weight_kg}
            elif measurement.type == "temperature":
                values = {"temperature_c": measurement.temperature_c}

            events.append(MeasurementEvent(
                measurement_id=measurement.id,
                timestamp=measurement.taken_at,
                measurement_type=measurement.type,
                source=measurement.source,
                device_name=device_name,
                values=values,
                recorded_by=measurement.recorded_by,
                recorded_by_name=recorded_by_name
            ))

    # 2. TAREAS
    if include_tasks:
        task_query = select(
            TaskApplication,
            TaskTemplate.name.label("task_name"),
            TaskCategory.name.label("task_category"),
            User.name.label("applied_by_name")
        ).join(
            TaskTemplate, TaskApplication.task_template_id == TaskTemplate.id
        ).join(
            TaskCategory, TaskTemplate.task_category_id == TaskCategory.id
        ).join(
            User, TaskApplication.applied_by == User.id, isouter=True
        ).where(
            TaskApplication.resident_id == id,
            TaskApplication.deleted_at.is_(None)
        )

        if date_from:
            task_query = task_query.where(TaskApplication.applied_at >= date_from)
        if date_to:
            task_query = task_query.where(TaskApplication.applied_at <= date_to)

        task_result = await db.execute(task_query)

        for task_app, task_name, task_category, applied_by_name in task_result.all():
            events.append(TaskEvent(
                task_application_id=task_app.id,
                timestamp=task_app.applied_at,
                task_name=task_name,
                task_category=task_category or "Sin categoría",
                status=task_app.selected_status_text,
                assigned_by=task_app.applied_by,
                assigned_by_name=applied_by_name,
                recorded_by=task_app.applied_by,
                recorded_by_name=applied_by_name
            ))

    # 3. CAMBIOS DE CAMA Y ESTADO
    if include_bed_changes or include_status_changes:
        # Crear alias para las tablas Room y Bed (previo y nuevo)
        PrevRoom = aliased(Room)
        PrevBed = aliased(Bed)

        history_query = select(
            ResidentHistory,
            User.name.label("changed_by_name"),
            PrevRoom.name.label("prev_room_name"),
            PrevBed.name.label("prev_bed_name")
        ).join(
            User, ResidentHistory.changed_by == User.id, isouter=True
        ).join(
            PrevRoom, ResidentHistory.previous_room_id == PrevRoom.id, isouter=True
        ).join(
            PrevBed, ResidentHistory.previous_bed_id == PrevBed.id, isouter=True
        ).where(
            ResidentHistory.resident_id == id
        )

        if date_from:
            history_query = history_query.where(ResidentHistory.changed_at >= date_from)
        if date_to:
            history_query = history_query.where(ResidentHistory.changed_at <= date_to)

        history_result = await db.execute(history_query)

        for history, changed_by_name, prev_room_name, prev_bed_name in history_result.all():
            # Cambios de cama
            if include_bed_changes and history.change_type in ['bed_assignment', 'bed_removal', 'residence_transfer']:
                # Obtener nombres de habitación y cama nuevos
                new_room = None
                new_bed = None
                if history.room_id:
                    room_result = await db.execute(select(Room.name).where(Room.id == history.room_id))
                    new_room = room_result.scalar()
                if history.bed_id:
                    bed_result = await db.execute(select(Bed.name).where(Bed.id == history.bed_id))
                    new_bed = bed_result.scalar()

                prev_location = f"{prev_room_name}, Cama {prev_bed_name}" if prev_room_name and prev_bed_name else None
                new_location = f"{new_room}, Cama {new_bed}" if new_room and new_bed else None

                events.append(BedChangeEvent(
                    history_id=history.id,
                    timestamp=history.changed_at,
                    change_type=history.change_type,
                    previous_location=prev_location,
                    new_location=new_location,
                    previous_bed_id=history.previous_bed_id,
                    new_bed_id=history.bed_id,
                    previous_room_id=history.previous_room_id,
                    new_room_id=history.room_id,
                    recorded_by=history.changed_by,
                    recorded_by_name=changed_by_name
                ))

            # Cambios de estado
            if include_status_changes and history.change_type == 'status_change':
                events.append(StatusChangeEvent(
                    history_id=history.id,
                    timestamp=history.changed_at,
                    previous_status=history.previous_status,
                    new_status=history.status,
                    recorded_by=history.changed_by,
                    recorded_by_name=changed_by_name
                ))

    # Ordenar eventos por timestamp descendente (más recientes primero)
    events.sort(key=lambda e: e.timestamp, reverse=True)

    # Aplicar límite
    events = events[:limit]

    # Calcular estadísticas
    total_measurements = sum(1 for e in events if e.event_type == "measurement")
    total_tasks = sum(1 for e in events if e.event_type == "task")
    total_bed_changes = sum(1 for e in events if e.event_type == "bed_change")
    total_status_changes = sum(1 for e in events if e.event_type == "status_change")

    return ResidentChronologyResponse(
        resident_id=id,
        resident_name=resident.full_name,
        events=events,
        total_events=len(events),
        total_measurements=total_measurements,
        total_tasks=total_tasks,
        total_bed_changes=total_bed_changes,
        total_status_changes=total_status_changes
    )


