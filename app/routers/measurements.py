# app/routers/measurements.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date
from typing import List

from app.deps import get_db, get_current_user
from app.security import new_uuid
from app.models import (
    Measurement, Resident, Device, UserResidence, Bed, User
)
from app.schemas import (
    MeasurementCreate, MeasurementOut, MeasurementUpdate, MeasurementDailySummary,
    PaginationParams, PaginatedResponse, FilterParams
)
from sqlalchemy import text

router = APIRouter(prefix="/measurements", tags=["measurements"])

# -------------------- helpers --------------------

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

def _check_measurement_fields_by_type(payload: MeasurementCreate | MeasurementUpdate):
    """
    Comprobaciones de coherencia rápida según el tipo:
      - bp: necesita al menos (systolic, diastolic) y puede venir pulse_bpm
      - spo2: requiere spo2 y puede pulse_bpm
      - weight: requiere weight_kg
      - temperature: requiere temperature_c
    """
    t = getattr(payload, "type", None)
    if t == "bp":
        if payload.systolic is None or payload.diastolic is None:
            raise HTTPException(status_code=400, detail="BP requires systolic and diastolic")
    elif t == "spo2":
        if payload.spo2 is None:
            raise HTTPException(status_code=400, detail="SpO2 requires spo2")
    elif t == "weight":
        if payload.weight_kg is None:
            raise HTTPException(status_code=400, detail="Weight requires weight_kg")
    elif t == "temperature":
        if payload.temperature_c is None:
            raise HTTPException(status_code=400, detail="Temperature requires temperature_c")

def _can_edit_delete(current: dict, recorder_id: str, role_manager_label: str = "manager") -> bool:
    if current["role"] == "superadmin":
        return True
    if current["role"] == role_manager_label:
        return True
    # professional: solo lo suyo
    return current["id"] == recorder_id

async def get_measurement_or_404(measurement_id: str, db: AsyncSession) -> Measurement:
    """Get measurement by ID or raise 404"""
    result = await db.execute(
        select(Measurement).where(Measurement.id == measurement_id, Measurement.deleted_at.is_(None))
    )
    measurement = result.scalar_one_or_none()
    if not measurement:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return measurement

async def paginate_query_measurements(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse[MeasurementOut]:
    """Apply pagination and filters to a measurements query"""

    if filter_params:
        if filter_params.date_from:
            query = query.where(Measurement.taken_at >= filter_params.date_from)
        if filter_params.date_to:
            query = query.where(Measurement.taken_at <= filter_params.date_to)
        if filter_params.type:
            query = query.where(Measurement.type == filter_params.type)
        if filter_params.search:
            search_term = f"%{filter_params.search}%"
            query = query.where(or_(
                Measurement.type.ilike(search_term),
                Measurement.source.ilike(search_term)
            ))

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    if pagination.sort_by:
        sort_field = getattr(Measurement, pagination.sort_by, Measurement.taken_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(Measurement.taken_at.desc())

    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)

    result = await db.execute(query)
    
    # Handle JOIN query - Measurement + resident_full_name + bed_name + recorded_by_name + device_name
    items = []
    for row in result.all():
        measurement, resident_full_name, bed_name, recorded_by_name, device_name = row
        item_dict = {
            "id": measurement.id,
            "residence_id": measurement.residence_id,
            "resident_id": measurement.resident_id,
            "resident_full_name": resident_full_name,
            "bed_name": bed_name,
            "recorded_by": measurement.recorded_by,
            "recorded_by_name": recorded_by_name,  # Nombre del profesional/gestor
            "source": measurement.source,
            "device_id": measurement.device_id,
            "device_name": device_name,  # Nombre del dispositivo
            "type": measurement.type,
            "systolic": measurement.systolic,
            "diastolic": measurement.diastolic,
            "pulse_bpm": measurement.pulse_bpm,
            "spo2": measurement.spo2,
            "weight_kg": measurement.weight_kg,
            "temperature_c": measurement.temperature_c,
            "taken_at": measurement.taken_at,
            "created_at": measurement.created_at,
            "updated_at": measurement.updated_at,
            "deleted_at": measurement.deleted_at
        }
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

# -------------------- endpoints --------------------

@router.post("", response_model=MeasurementOut)
async def create_measurement(
    payload: MeasurementCreate,
    db: AsyncSession = Depends(get_db),                     # fija app.user_id
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """
    Crea una medición. Si el header residence_id no llega, se intenta inferir
    a partir de resident_id o device_id. Valida pertenencia y coherencia de datos.
    """
    # Validación por tipo
    _check_measurement_fields_by_type(payload)

    # Fijar / inferir residencia y validar acceso
    rid = await apply_residence_context_or_infer(
        db, current, residence_id, resident_id=payload.resident_id, device_id=payload.device_id
    )

    # Coherencia de residente y (opcional) dispositivo dentro de la residencia
    res_ok = await db.scalar(
        select(Resident.id).where(
            Resident.id == payload.resident_id,
            Resident.residence_id == rid,
            Resident.deleted_at.is_(None),
        )
    )
    if not res_ok:
        raise HTTPException(status_code=400, detail="Resident does not belong to selected residence")

    if payload.device_id:
        dev_ok = await db.scalar(
            select(Device.id).where(
                Device.id == payload.device_id,
                Device.residence_id == rid,
                Device.deleted_at.is_(None),
            )
        )
        if not dev_ok:
            raise HTTPException(status_code=400, detail="Device does not belong to selected residence")

    m = Measurement(
        id=new_uuid(),
        residence_id=rid,
        resident_id=payload.resident_id,
        recorded_by=current["id"],
        source=payload.source,             # 'device' | 'voice' | 'manual'
        device_id=payload.device_id,
        type=payload.type,                 # 'bp' | 'spo2' | 'weight' | 'temperature'
        systolic=payload.systolic,
        diastolic=payload.diastolic,
        pulse_bpm=payload.pulse_bpm,
        spo2=payload.spo2,
        weight_kg=payload.weight_kg,
        temperature_c=payload.temperature_c,
        taken_at=payload.taken_at,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m

@router.get("/", response_model=PaginatedResponse[MeasurementOut])
async def list_measurements(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    resident_id: str | None = Query(None),
) -> PaginatedResponse[MeasurementOut]:
    """
    List measurements with pagination and filters
    """
    rid = await apply_residence_context_or_infer(db, current, residence_id, resident_id=resident_id)

    # Query with JOINs to get additional information including names
    query = select(
        Measurement,
        Resident.full_name.label("resident_full_name"),
        Bed.name.label("bed_name"),
        User.name.label("recorded_by_name"),  # Nombre del profesional/gestor
        Device.name.label("device_name")      # Nombre del dispositivo
    ).join(
        Resident, Measurement.resident_id == Resident.id
    ).join(
        Bed, Resident.bed_id == Bed.id, isouter=True
    ).join(
        User, Measurement.recorded_by == User.id  # JOIN para obtener nombre del usuario
    ).join(
        Device, Measurement.device_id == Device.id, isouter=True  # JOIN para obtener nombre del dispositivo
    ).where(
        Measurement.residence_id == rid, 
        Measurement.deleted_at.is_(None),
        Resident.deleted_at.is_(None),
        User.deleted_at.is_(None)  # Solo usuarios activos
    )

    if resident_id:
        query = query.where(Measurement.resident_id == resident_id)

    # Apply filters from FilterParams
    if filters:
        if filters.date_from:
            query = query.where(Measurement.taken_at >= filters.date_from)
        if filters.date_to:
            query = query.where(Measurement.taken_at <= filters.date_to)
        if filters.type:
            query = query.where(Measurement.type == filters.type)
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.where(or_(
                Measurement.type.ilike(search_term),
                Measurement.source.ilike(search_term)
            ))

    return await paginate_query_measurements(query, db, pagination, filters)

@router.get("/simple", response_model=list[MeasurementOut])
async def list_measurements_simple(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    resident_id: str | None = Query(None),
    type: str | None = Query(None, description="bp|spo2|weight|temperature"),
    since: str | None = Query(None, description="ISO datetime"),
    until: str | None = Query(None, description="ISO datetime"),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Legacy endpoint: List measurements without pagination
    """
    rid = await apply_residence_context_or_infer(db, current, residence_id, resident_id=resident_id)

    conds = [Measurement.residence_id == rid, Measurement.deleted_at.is_(None)]
    if resident_id:
        conds.append(Measurement.resident_id == resident_id)
    if type:
        conds.append(Measurement.type == type)
    if since:
        conds.append(Measurement.taken_at >= since)
    if until:
        conds.append(Measurement.taken_at <= until)

    q = await db.execute(
        select(Measurement).where(and_(*conds)).order_by(Measurement.taken_at.desc()).limit(limit)
    )
    return q.scalars().all()

# -------------------- ENDPOINTS ESPECÍFICOS (ANTES DEL GENÉRICO) --------------------

async def paginate_query_daily_summary(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse[MeasurementDailySummary]:
    """Apply pagination and filters to a daily summary query"""
    
    # Apply filters
    if filter_params:
        if filter_params.date_from:
            query = query.where(func.date(Measurement.taken_at) >= filter_params.date_from.date())
        if filter_params.date_to:
            query = query.where(func.date(Measurement.taken_at) <= filter_params.date_to.date())
        if filter_params.search:
            search_term = f"%{filter_params.search}%"
            query = query.where(Resident.full_name.ilike(search_term))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)
    
    # Execute query
    result = await db.execute(query)
    rows = result.all()
    
    # Convert to MeasurementDailySummary objects
    items = []
    for row in rows:
        summary = MeasurementDailySummary(
            resident_id=str(row.resident_id),
            resident_full_name=row.resident_full_name,
            bed_name=row.bed_name,
            date=row.date,
            measurement_count=row.measurement_count,
            measurement_types=row.measurement_types,
            first_measurement_time=row.first_measurement_time,
            last_measurement_time=row.last_measurement_time
        )
        items.append(summary)
    
    # Calculate pagination info
    pages = (total + pagination.size - 1) // pagination.size
    
    return PaginatedResponse[MeasurementDailySummary](
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages,
        has_next=pagination.page < pages,
        has_prev=pagination.page > 1
    )

@router.get("/daily-summary", response_model=PaginatedResponse[MeasurementDailySummary])
async def get_daily_summary(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
) -> PaginatedResponse[MeasurementDailySummary]:
    """
    Obtiene un resumen diario de mediciones agrupadas por residente y fecha.
    
    Retorna un registro por cada residente/día que tenga mediciones, con información
    agregada como cantidad de mediciones, tipos realizados y horarios.
    """
    rid = await apply_residence_context_or_infer(db, current, residence_id)
    
    # Query with JOINs and GROUP BY using SQLAlchemy ORM
    query = select(
        Resident.id.label("resident_id"),
        Resident.full_name.label("resident_full_name"),
        Bed.name.label("bed_name"),
        func.date(Measurement.taken_at).label("date"),
        func.count(Measurement.id).label("measurement_count"),
        func.array_agg(func.distinct(Measurement.type)).label("measurement_types"),
        func.min(func.to_char(Measurement.taken_at, 'HH24:MI:SS')).label("first_measurement_time"),
        func.max(func.to_char(Measurement.taken_at, 'HH24:MI:SS')).label("last_measurement_time")
    ).select_from(
        Measurement.__table__
        .join(Resident.__table__, Measurement.resident_id == Resident.id)
        .join(Bed.__table__, Resident.bed_id == Bed.id, isouter=True)
    ).where(
        Measurement.residence_id == rid,
        Measurement.deleted_at.is_(None),
        Resident.deleted_at.is_(None)
    ).group_by(
        Resident.id,
        Resident.full_name,
        Bed.name,
        func.date(Measurement.taken_at)
    ).order_by(
        func.date(Measurement.taken_at).desc(),
        Resident.full_name.asc()
    )
    
    return await paginate_query_daily_summary(query, db, pagination, filters)


@router.get("/by-day", response_model=List[MeasurementOut])
async def get_measurements_by_day(
    resident_id: str = Query(..., description="ID del residente"),
    date: str = Query(..., description="Fecha específica (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> List[MeasurementOut]:
    """
    Obtiene todas las mediciones de un residente en una fecha específica.
    
    Retorna todas las mediciones del residente para el día especificado,
    ordenadas cronológicamente por hora de toma.
    """
    # Validar formato de fecha
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date debe estar en formato YYYY-MM-DD")
    
    # Construir query con JOINs para obtener datos completos incluyendo nombres
    query = select(
        Measurement,
        Resident.full_name.label("resident_full_name"),
        Bed.name.label("bed_name"),
        User.name.label("recorded_by_name"),  # Nombre del profesional/gestor
        Device.name.label("device_name")      # Nombre del dispositivo
    ).join(
        Resident, Measurement.resident_id == Resident.id
    ).join(
        Bed, Resident.bed_id == Bed.id, isouter=True
    ).join(
        User, Measurement.recorded_by == User.id  # JOIN para obtener nombre del usuario
    ).join(
        Device, Measurement.device_id == Device.id, isouter=True  # JOIN para obtener nombre del dispositivo
    ).where(
        and_(
            Measurement.resident_id == resident_id,
            func.date(Measurement.taken_at) == target_date,
            Measurement.deleted_at.is_(None),
            Resident.deleted_at.is_(None),
            User.deleted_at.is_(None)  # Solo usuarios activos
        )
    ).order_by(Measurement.taken_at.asc())
    
    # Ejecutar query
    result = await db.execute(query)
    rows = result.all()
    
    # Convertir a objetos MeasurementOut con nombres completos
    measurements = []
    for row in rows:
        measurement, resident_full_name, bed_name, recorded_by_name, device_name = row
        measurement_dict = {
            "id": measurement.id,
            "residence_id": measurement.residence_id,
            "resident_id": measurement.resident_id,
            "resident_full_name": resident_full_name,
            "bed_name": bed_name,
            "recorded_by": measurement.recorded_by,
            "recorded_by_name": recorded_by_name,  # Nombre del profesional/gestor
            "source": measurement.source,
            "device_id": measurement.device_id,
            "device_name": device_name,  # Nombre del dispositivo
            "type": measurement.type,
            "systolic": measurement.systolic,
            "diastolic": measurement.diastolic,
            "pulse_bpm": measurement.pulse_bpm,
            "spo2": measurement.spo2,
            "weight_kg": measurement.weight_kg,
            "temperature_c": measurement.temperature_c,
            "taken_at": measurement.taken_at,
            "created_at": measurement.created_at,
            "updated_at": measurement.updated_at,
            "deleted_at": measurement.deleted_at
        }
        measurements.append(MeasurementOut(**measurement_dict))
    
    return measurements

@router.get("/residents/{resident_id}/measurements", response_model=List[MeasurementOut])
async def get_resident_measurements_by_type(
    resident_id: str,
    type: str = Query(..., description="Tipo de medición (bp, spo2, weight, temperature)"),
    size: int = Query(10, ge=1, le=100, description="Número de mediciones a devolver (1-100)"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> List[MeasurementOut]:
    """
    Obtiene las últimas N mediciones de un tipo específico para un residente.
    
    Retorna las mediciones más recientes del tipo especificado para el residente,
    ordenadas por fecha de toma descendente (más recientes primero).
    
    Args:
        resident_id: ID del residente
        type: Tipo de medición (bp, spo2, weight, temperature)
        size: Número de mediciones a devolver (máximo 100)
    """
    # Validar tipo de medición
    valid_types = ["bp", "spo2", "weight", "temperature"]
    if type not in valid_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de medición inválido. Tipos válidos: {', '.join(valid_types)}"
        )
    
    # Construir query con JOINs para obtener datos completos incluyendo nombres
    query = select(
        Measurement,
        Resident.full_name.label("resident_full_name"),
        Bed.name.label("bed_name"),
        User.name.label("recorded_by_name"),  # Nombre del profesional/gestor
        Device.name.label("device_name")      # Nombre del dispositivo
    ).join(
        Resident, Measurement.resident_id == Resident.id
    ).join(
        Bed, Resident.bed_id == Bed.id, isouter=True
    ).join(
        User, Measurement.recorded_by == User.id  # JOIN para obtener nombre del usuario
    ).join(
        Device, Measurement.device_id == Device.id, isouter=True  # JOIN para obtener nombre del dispositivo
    ).where(
        and_(
            Measurement.resident_id == resident_id,
            Measurement.type == type,
            Measurement.deleted_at.is_(None),
            Resident.deleted_at.is_(None),
            User.deleted_at.is_(None)  # Solo usuarios activos
        )
    ).order_by(Measurement.taken_at.desc()).limit(size)
    
    # Ejecutar query
    result = await db.execute(query)
    rows = result.all()
    
    # Convertir a objetos MeasurementOut con nombres completos
    measurements = []
    for row in rows:
        measurement, resident_full_name, bed_name, recorded_by_name, device_name = row
        measurement_dict = {
            "id": measurement.id,
            "residence_id": measurement.residence_id,
            "resident_id": measurement.resident_id,
            "resident_full_name": resident_full_name,
            "bed_name": bed_name,
            "recorded_by": measurement.recorded_by,
            "recorded_by_name": recorded_by_name,  # Nombre del profesional/gestor
            "source": measurement.source,
            "device_id": measurement.device_id,
            "device_name": device_name,  # Nombre del dispositivo
            "type": measurement.type,
            "systolic": measurement.systolic,
            "diastolic": measurement.diastolic,
            "pulse_bpm": measurement.pulse_bpm,
            "spo2": measurement.spo2,
            "weight_kg": measurement.weight_kg,
            "temperature_c": measurement.temperature_c,
            "taken_at": measurement.taken_at,
            "created_at": measurement.created_at,
            "updated_at": measurement.updated_at,
            "deleted_at": measurement.deleted_at
        }
        measurements.append(MeasurementOut(**measurement_dict))
    
    return measurements

# -------------------- ENDPOINTS GENÉRICOS --------------------

@router.get("/{measurement_id}", response_model=MeasurementOut)
async def get_measurement(
    measurement_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Get a specific measurement"""
    measurement = await get_measurement_or_404(measurement_id, db)

    # Fijar/validar residencia respecto a la medición
    await apply_residence_context_or_infer(db, current, residence_id, resident_id=measurement.resident_id)

    return measurement

@router.put("/{measurement_id}", response_model=MeasurementOut)
async def update_measurement(
    measurement_id: str,
    payload: MeasurementUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Update a measurement"""
    measurement = await get_measurement_or_404(measurement_id, db)

    # Contexto/validación de residencia
    rid = await apply_residence_context_or_infer(db, current, residence_id, resident_id=measurement.resident_id)

    # Permisos: superadmin/manager cualquiera; professional solo si es suyo
    if not _can_edit_delete(current, measurement.recorded_by):
        raise HTTPException(status_code=403, detail="You cannot edit this measurement")

    # Validación de tipo si lo cambia (normalmente no se cambia el tipo)
    if payload.type is not None and payload.type != measurement.type:
        _check_measurement_fields_by_type(payload)

    # Validar device si lo cambian
    if payload.device_id:
        dev_ok = await db.scalar(
            select(Device.id).where(
                Device.id == payload.device_id,
                Device.residence_id == rid,
                Device.deleted_at.is_(None),
            )
        )
        if not dev_ok:
            raise HTTPException(status_code=400, detail="Device does not belong to selected residence")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(measurement, field, value)

    await db.commit()
    await db.refresh(measurement)
    return measurement

@router.patch("/{measurement_id}", response_model=MeasurementOut)
async def patch_measurement(
    measurement_id: str,
    payload: MeasurementUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Patch a measurement (legacy endpoint)"""
    return await update_measurement(measurement_id, payload, db, current, residence_id)

@router.delete("/{measurement_id}", status_code=204)
async def delete_measurement(
    measurement_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Soft delete a measurement"""
    measurement = await get_measurement_or_404(measurement_id, db)

    await apply_residence_context_or_infer(db, current, residence_id, resident_id=measurement.resident_id)

    if not _can_edit_delete(current, measurement.recorded_by):
        raise HTTPException(status_code=403, detail="You cannot delete this measurement")

    await db.execute(
        update(Measurement).where(Measurement.id == measurement_id).values(deleted_at=func.now(), updated_at=func.now())
    )
    await db.commit()

# -------------------- Additional Endpoints --------------------

@router.get("/residents/{resident_id}/measurements", response_model=PaginatedResponse[MeasurementOut])
async def get_measurements_by_resident(
    resident_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
    type: str | None = Query(None, description="Filter by measurement type: bp|spo2|weight|temperature"),
    time_filter: str = Query("all", description="Time filter: 7d|15d|30d|1y|all"),
) -> PaginatedResponse[MeasurementOut]:
    """
    Get measurements for a specific resident with time filters.
    
    Time filters:
    - 7d: Last 7 days
    - 15d: Last 15 days  
    - 30d: Last 30 days
    - 1y: Last year
    - all: All measurements
    """
    from datetime import datetime, timedelta
    
    # Validate time filter
    valid_filters = ["7d", "15d", "30d", "1y", "all"]
    if time_filter not in valid_filters:
        raise HTTPException(status_code=400, detail=f"Invalid time_filter. Must be one of: {valid_filters}")
    
    # Apply residence context
    rid = await apply_residence_context_or_infer(db, current, residence_id, resident_id=resident_id)
    
    # Validate resident exists and belongs to residence
    resident_check = await db.scalar(
        select(Resident.id).where(
            Resident.id == resident_id,
            Resident.residence_id == rid,
            Resident.deleted_at.is_(None)
        )
    )
    if not resident_check:
        raise HTTPException(status_code=404, detail="Resident not found or not accessible")
    
    # Build base query with resident name and bed name
    query = select(
        Measurement,
        Resident.full_name.label("resident_full_name"),
        Bed.name.label("bed_name")
    ).join(
        Resident, Measurement.resident_id == Resident.id
    ).join(
        Bed, Resident.bed_id == Bed.id, isouter=True  # LEFT JOIN porque bed_id puede ser NULL
    ).where(
        Measurement.resident_id == resident_id,
        Measurement.residence_id == rid,
        Measurement.deleted_at.is_(None),
        Resident.deleted_at.is_(None)
    )
    
    # Apply time filter
    if time_filter != "all":
        now = datetime.utcnow()
        time_deltas = {
            "7d": timedelta(days=7),
            "15d": timedelta(days=15),
            "30d": timedelta(days=30),
            "1y": timedelta(days=365)
        }
        date_from = now - time_deltas[time_filter]
        query = query.where(Measurement.taken_at >= date_from)
    
    # Apply type filter
    if type:
        if type not in ["bp", "spo2", "weight", "temperature"]:
            raise HTTPException(status_code=400, detail="Invalid type. Must be: bp|spo2|weight|temperature")
        query = query.where(Measurement.type == type)
    
    # Order by most recent first
    query = query.order_by(Measurement.taken_at.desc())
    
    # Custom pagination to handle the join
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    offset = (pagination.page - 1) * pagination.size
    result = await db.execute(query.offset(offset).limit(pagination.size))
    
    items = []
    for row in result.all():
        measurement, resident_full_name, bed_name = row
        
        # Build item dictionary with resident name and bed name
        item_dict = {
            "id": measurement.id,
            "residence_id": measurement.residence_id,
            "resident_id": measurement.resident_id,
            "resident_full_name": resident_full_name,
            "bed_name": bed_name,
            "recorded_by": measurement.recorded_by,
            "source": measurement.source,
            "device_id": measurement.device_id,
            "type": measurement.type,
            "systolic": measurement.systolic,
            "diastolic": measurement.diastolic,
            "pulse_bpm": measurement.pulse_bpm,
            "spo2": measurement.spo2,
            "weight_kg": measurement.weight_kg,
            "temperature_c": measurement.temperature_c,
            "taken_at": measurement.taken_at,
            "created_at": measurement.created_at,
            "updated_at": measurement.updated_at,
            "deleted_at": measurement.deleted_at
        }
        items.append(item_dict)
    
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

@router.get("/{measurement_id}/history", response_model=list[dict])
async def get_measurement_history(
    measurement_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, description="Filter by residence ID"),
):
    """Get measurement history"""
    measurement = await get_measurement_or_404(measurement_id, db)

    await apply_residence_context_or_infer(db, current, residence_id, resident_id=measurement.resident_id)

    result = await db.execute(
        text("""
            SELECT h.*
            FROM measurement_history h
            WHERE h.measurement_id = :measurement_id
            ORDER BY h.valid_from DESC
        """),
        {"measurement_id": measurement_id}
    )

    return [dict(row._mapping) for row in result.fetchall()]


