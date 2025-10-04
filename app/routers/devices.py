from __future__ import annotations

from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_db, get_current_user
from app.models import Device, Residence, User, UserResidence
from app.schemas import (
    DeviceCreate, DeviceUpdate, DeviceOut,
    PaginationParams, PaginatedResponse, FilterParams
)
from app.security import new_uuid

router = APIRouter(prefix="/devices", tags=["devices"])

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

async def get_device_or_404(device_id: str, db: AsyncSession) -> Device:
    """Get device by ID or raise 404"""
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.deleted_at.is_(None))
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

async def paginate_query_devices(
    query,
    db: AsyncSession,
    pagination: PaginationParams,
    filter_params: FilterParams = None
) -> PaginatedResponse[DeviceOut]:
    """Apply pagination and filters to a devices query"""

    if filter_params:
        if filter_params.date_from:
            query = query.where(Device.created_at >= filter_params.date_from)
        if filter_params.date_to:
            query = query.where(Device.created_at <= filter_params.date_to)
        if filter_params.type:
            query = query.where(Device.type == filter_params.type)
        if filter_params.search:
            search_term = f"%{filter_params.search}%"
            query = query.where(or_(
                Device.name.ilike(search_term),
                Device.mac.ilike(search_term)
            ))

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    if pagination.sort_by:
        sort_field = getattr(Device, pagination.sort_by, Device.created_at)
        if pagination.sort_order == 'desc':
            sort_field = sort_field.desc()
        query = query.order_by(sort_field)
    else:
        query = query.order_by(Device.created_at.desc())

    offset = (pagination.page - 1) * pagination.size
    query = query.offset(offset).limit(pagination.size)

    result = await db.execute(query)
    devices = result.scalars().all()
    
    # Agregar created_by_info y residence_info a cada dispositivo
    items = []
    for device in devices:
        item = {
            "id": device.id,
            "residence_id": device.residence_id,
            "type": device.type,
            "name": device.name,
            "mac": device.mac,
            "battery_percent": device.battery_percent,
            "created_at": device.created_at,
            "updated_at": device.updated_at,
            "deleted_at": device.deleted_at
        }
        
        # Obtener información del usuario creador
        if device.created_by:
            from app.security import decrypt_data
            creator_result = await db.execute(
                select(User.name, User.alias_encrypted).where(User.id == device.created_by)
            )
            creator = creator_result.first()
            if creator:
                creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
                item["created_by_info"] = {
                    "id": device.created_by,
                    "name": creator[0],
                    "alias": creator_alias
                }
            else:
                item["created_by_info"] = None
        else:
            item["created_by_info"] = None

        # Obtener información de la residencia
        residence_result = await db.execute(
            select(Residence.name).where(Residence.id == device.residence_id)
        )
        residence_name = residence_result.scalar()
        item["residence_info"] = {
            "id": device.residence_id,
            "name": residence_name
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

# -------------------- CRUD Endpoints --------------------

@router.post("/", response_model=DeviceOut, status_code=201)
async def create_device(
    data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="residence_id"),
):
    """Create a new device"""
    await apply_residence_context(db, current, residence_id)

    if not residence_id:
        raise HTTPException(status_code=400, detail="Residence ID is required")

    existing = await db.scalar(
        select(Device.id).where(
            Device.residence_id == residence_id,
            Device.mac == data.mac,
            Device.deleted_at.is_(None)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Device MAC already exists in this residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    device = Device(
        id=new_uuid(),
        residence_id=residence_id,
        **data.model_dump(),
        created_by=current["id"]
    )

    db.add(device)
    await db.commit()
    await db.refresh(device)

    # Obtener información del usuario creador
    from app.security import decrypt_data
    created_by_info = None
    if device.created_by:
        creator_result = await db.execute(
            select(User.name, User.alias_encrypted).where(User.id == device.created_by)
        )
        creator = creator_result.first()
        if creator:
            creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
            created_by_info = {
                "id": device.created_by,
                "name": creator[0],
                "alias": creator_alias
            }

    # Obtener información de la residencia
    residence_result = await db.execute(
        select(Residence.name).where(Residence.id == device.residence_id)
    )
    residence_name = residence_result.scalar()
    residence_info = {
        "id": device.residence_id,
        "name": residence_name
    }

    # Construir respuesta manualmente
    return {
        "id": device.id,
        "residence_id": device.residence_id,
        "residence_info": residence_info,
        "type": device.type,
        "name": device.name,
        "mac": device.mac,
        "battery_percent": device.battery_percent,
        "created_by_info": created_by_info,
        "created_at": device.created_at,
        "updated_at": device.updated_at,
        "deleted_at": device.deleted_at
    }

@router.get("/", response_model=PaginatedResponse[DeviceOut])
async def list_devices(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Query(None, alias="residence_id"),
) -> PaginatedResponse[DeviceOut]:
    """List devices with pagination and filters"""
    query = select(Device).where(Device.deleted_at.is_(None))

    if current["role"] != "superadmin":
        # Gestores y profesionales: mostrar dispositivos de sus residencias asignadas
        user_residences_result = await db.execute(
            select(UserResidence.residence_id).where(
                UserResidence.user_id == current["id"],
                UserResidence.deleted_at.is_(None)
            )
        )
        allowed_residence_ids = [row[0] for row in user_residences_result.all()]

        if not allowed_residence_ids:
            raise HTTPException(status_code=403, detail="No residences assigned")

        # Si se proporciona residence_id, verificar que el usuario tenga acceso
        if residence_id:
            if residence_id not in allowed_residence_ids:
                raise HTTPException(status_code=403, detail="Access denied to this residence")
            query = query.where(Device.residence_id == residence_id)
        else:
            # Sin residence_id: mostrar dispositivos de todas las residencias asignadas
            query = query.where(Device.residence_id.in_(allowed_residence_ids))
    elif residence_id:
        # Superadmin con residence_id específico: filtrar por esa residencia
        query = query.where(Device.residence_id == residence_id)

    return await paginate_query_devices(query, db, pagination, filters)

@router.get("/{id}", response_model=DeviceOut)
async def get_device(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get a specific device"""
    device = await get_device_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == device.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this device")

    # Obtener información del usuario creador
    created_by_info = None
    if device.created_by:
        from app.security import decrypt_data
        creator_result = await db.execute(
            select(User.name, User.alias_encrypted).where(User.id == device.created_by)
        )
        creator = creator_result.first()
        if creator:
            creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
            created_by_info = {
                "id": device.created_by,
                "name": creator[0],
                "alias": creator_alias
            }

    # Obtener información de la residencia
    residence_result = await db.execute(
        select(Residence.name).where(Residence.id == device.residence_id)
    )
    residence_name = residence_result.scalar()
    residence_info = {
        "id": device.residence_id,
        "name": residence_name
    }

    # Construir respuesta manualmente
    return {
        "id": device.id,
        "residence_id": device.residence_id,
        "residence_info": residence_info,
        "type": device.type,
        "name": device.name,
        "mac": device.mac,
        "battery_percent": device.battery_percent,
        "created_by_info": created_by_info,
        "created_at": device.created_at,
        "updated_at": device.updated_at,
        "deleted_at": device.deleted_at
    }

@router.put("/{id}", response_model=DeviceOut)
async def update_device(
    id: str,
    data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Update a device"""
    device = await get_device_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == device.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this device")

    if data.mac and data.mac != device.mac:
        existing = await db.scalar(
            select(Device.id).where(
                Device.residence_id == device.residence_id,
                Device.mac == data.mac,
                Device.id != id,
                Device.deleted_at.is_(None)
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Device MAC already exists in this residence")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)

    await db.commit()
    await db.refresh(device)

    # Obtener información del usuario creador
    created_by_info = None
    if device.created_by:
        from app.security import decrypt_data
        creator_result = await db.execute(
            select(User.name, User.alias_encrypted).where(User.id == device.created_by)
        )
        creator = creator_result.first()
        if creator:
            creator_alias = decrypt_data(creator[1]) if creator[1] else "N/A"
            created_by_info = {
                "id": device.created_by,
                "name": creator[0],
                "alias": creator_alias
            }

    # Obtener información de la residencia
    residence_result = await db.execute(
        select(Residence.name).where(Residence.id == device.residence_id)
    )
    residence_name = residence_result.scalar()
    residence_info = {
        "id": device.residence_id,
        "name": residence_name
    }

    # Construir respuesta manualmente
    return {
        "id": device.id,
        "residence_id": device.residence_id,
        "residence_info": residence_info,
        "type": device.type,
        "name": device.name,
        "mac": device.mac,
        "battery_percent": device.battery_percent,
        "created_by_info": created_by_info,
        "created_at": device.created_at,
        "updated_at": device.updated_at,
        "deleted_at": device.deleted_at
    }

@router.delete("/{id}", status_code=204)
async def delete_device(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Soft delete a device"""
    device = await get_device_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == device.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this device")

    await db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

    device.deleted_at = func.now()
    await db.commit()

# -------------------- Additional Endpoints --------------------

@router.get("/{id}/history", response_model=list[dict])
async def get_device_history(
    id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
):
    """Get device history"""
    device = await get_device_or_404(id, db)

    if current["role"] != "superadmin":
        result = await db.execute(
            select(UserResidence).where(
                UserResidence.user_id == current["id"],
                UserResidence.residence_id == device.residence_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Access denied to this device")

    result = await db.execute(
        text("""
            SELECT h.*
            FROM device_history h
            WHERE h.device_id = :device_id
            ORDER BY h.valid_from DESC
        """),
        {"device_id": id}
    )

    return [dict(row._mapping) for row in result.fetchall()]



