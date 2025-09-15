# app/routers/measurements.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.security import new_uuid
from app.models import (
    Measurement, Resident, Device, UserResidence
)
from app.schemas import (
    MeasurementCreate, MeasurementOut, MeasurementUpdate
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
            detail="Select a residence (send X-Residence-Id or include resident_id/device_id to infer)"
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

# -------------------- endpoints --------------------

@router.post("", response_model=MeasurementOut)
async def create_measurement(
    payload: MeasurementCreate,
    db: AsyncSession = Depends(get_db),                     # fija app.user_id
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    """
    Crea una medición. Si el header X-Residence-Id no llega, se intenta inferir
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

@router.get("", response_model=list[MeasurementOut])
async def list_measurements(
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
    resident_id: str | None = Query(None),
    type: str | None = Query(None, description="bp|spo2|weight|temperature"),
    since: str | None = Query(None, description="ISO datetime"),
    until: str | None = Query(None, description="ISO datetime"),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Lista mediciones en la residencia del contexto (o inferida por resident_id / device_id).
    Filtros opcionales: resident_id, type, rango de fechas.
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

@router.get("/{measurement_id}", response_model=MeasurementOut)
async def get_measurement(
    measurement_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    # Traer la medición
    q = await db.execute(select(Measurement).where(Measurement.id == measurement_id, Measurement.deleted_at.is_(None)))
    m = q.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Measurement not found")

    # Fijar/validar residencia respecto a la medición
    await apply_residence_context_or_infer(db, current, residence_id, resident_id=m.resident_id)

    return m

@router.patch("/{measurement_id}", response_model=MeasurementOut)
async def update_measurement(
    measurement_id: str,
    payload: MeasurementUpdate,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    q = await db.execute(select(Measurement).where(Measurement.id == measurement_id, Measurement.deleted_at.is_(None)))
    m = q.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Measurement not found")

    # Contexto/validación de residencia
    rid = await apply_residence_context_or_infer(db, current, residence_id, resident_id=m.resident_id)

    # Permisos: superadmin/manager cualquiera; professional solo si es suyo
    if not _can_edit_delete(current, m.recorded_by):
        raise HTTPException(status_code=403, detail="You cannot edit this measurement")

    # Validación de tipo si lo cambia (normalmente no se cambia el tipo)
    if payload.type is not None and payload.type != m.type:
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

    changes = {
        "source": payload.source if payload.source is not None else m.source,
        "device_id": payload.device_id if payload.device_id is not None else m.device_id,
        "type": payload.type if payload.type is not None else m.type,
        "systolic": payload.systolic if payload.systolic is not None else m.systolic,
        "diastolic": payload.diastolic if payload.diastolic is not None else m.diastolic,
        "pulse_bpm": payload.pulse_bpm if payload.pulse_bpm is not None else m.pulse_bpm,
        "spo2": payload.spo2 if payload.spo2 is not None else m.spo2,
        "weight_kg": payload.weight_kg if payload.weight_kg is not None else m.weight_kg,
        "temperature_c": payload.temperature_c if payload.temperature_c is not None else m.temperature_c,
        "taken_at": payload.taken_at if payload.taken_at is not None else m.taken_at,
        "updated_at": func.now(),
    }

    await db.execute(
        update(Measurement).where(Measurement.id == measurement_id).values(**changes)
    )
    await db.commit()

    # devolver el registro actualizado
    q2 = await db.execute(select(Measurement).where(Measurement.id == measurement_id))
    return q2.scalar_one()

@router.delete("/{measurement_id}", status_code=204)
async def delete_measurement(
    measurement_id: str,
    db: AsyncSession = Depends(get_db),
    current = Depends(get_current_user),
    residence_id: str | None = Header(None, alias="X-Residence-Id"),
):
    q = await db.execute(select(Measurement).where(Measurement.id == measurement_id, Measurement.deleted_at.is_(None)))
    m = q.scalar_one_or_none()
    if not m:
        # ya estaba borrada o no existe
        return

    await apply_residence_context_or_infer(db, current, residence_id, resident_id=m.resident_id)

    if not _can_edit_delete(current, m.recorded_by):
        raise HTTPException(status_code=403, detail="You cannot delete this measurement")

    await db.execute(
        update(Measurement).where(Measurement.id == measurement_id).values(deleted_at=func.now(), updated_at=func.now())
    )
    await db.commit()
