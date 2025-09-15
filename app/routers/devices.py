from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db, get_current_user
from app.models import Device
from app.schemas import DeviceCreate, DeviceOut

router = APIRouter(prefix="/devices", tags=["devices"])

@router.post("", response_model=DeviceOut, status_code=201)
async def create_device(payload: DeviceCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    d = Device(**payload.model_dump(), created_by=user["id"])
    db.add(d); await db.commit(); await db.refresh(d)
    return d

@router.get("", response_model=list[DeviceOut])
async def list_devices(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Device).where(Device.deleted_at.is_(None)))
    return r.scalars().all()



