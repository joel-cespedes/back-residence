from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db
from app.models import Floor, Room, Bed

router = APIRouter(prefix="/structure", tags=["structure"])

@router.get("/floors/{residence_id}")
async def floors(residence_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Floor).where(Floor.residence_id==residence_id, Floor.deleted_at.is_(None)))
    return [ {"id": f.id, "name": f.name} for f in r.scalars().all() ]

@router.get("/rooms/{floor_id}")
async def rooms(floor_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Room).where(Room.floor_id==floor_id, Room.deleted_at.is_(None)))
    return [ {"id": x.id, "name": x.name} for x in r.scalars().all() ]

@router.get("/beds/{room_id}")
async def beds(room_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Bed).where(Bed.room_id==room_id, Bed.deleted_at.is_(None)))
    return [ {"id": x.id, "name": x.name} for x in r.scalars().all() ]



