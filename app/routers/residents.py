from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.deps import get_db, get_current_user
from app.models import Resident, Bed
from app.schemas import ResidentCreate, ResidentOut, ResidentChangeBed

router = APIRouter(prefix="/residents", tags=["residents"])

@router.post("", response_model=ResidentOut, status_code=201)
async def create_resident(payload: ResidentCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    res = Resident(**payload.model_dump(), status='active')
    db.add(res); await db.commit(); await db.refresh(res)
    return res

@router.get("", response_model=list[ResidentOut])
async def list_residents(db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(Resident).where(Resident.deleted_at.is_(None)))
    return q.scalars().all()

@router.patch("/{resident_id}/bed", response_model=ResidentOut)
async def change_bed(resident_id: str, payload: ResidentChangeBed, db: AsyncSession = Depends(get_db)):
    # el trigger en BD valida residencia y registra event_log
    q = await db.execute(select(Resident).where(Resident.id==resident_id))
    r = q.scalar_one_or_none()
    if not r: raise HTTPException(404, "resident not found")
    r.bed_id = payload.bed_id
    await db.commit(); await db.refresh(r)
    return r


