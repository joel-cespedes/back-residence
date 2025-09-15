from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db
from app.models import Tag, ResidentTag

router = APIRouter(prefix="/tags", tags=["tags"])

@router.get("")
async def list_tags(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Tag).where(Tag.deleted_at.is_(None)))
    return [{"id": t.id, "name": t.name} for t in r.scalars().all()]



