from __future__ import annotations

from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.db import AsyncSessionLocal
from app.security import decode_token
from app.models import UserResidence

bearer = HTTPBearer(auto_error=False)

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        result = {"id": payload["sub"], "role": payload["role"]}
        if "alias" in payload:
            result["alias"] = payload["alias"]
        return result
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

async def get_db(current=Depends(get_current_user)) -> AsyncSession:
    """
    Sesión con app.user_id configurado para RLS/auditoría.
    No obliga a elegir residencia.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})
        yield session

async def get_db_with_residence(
    current = Depends(get_current_user),
    residence_id_query: str | None = Query(None, alias="residenceId"),
    residence_id_header: str | None = Header(None, alias="residence-id"),
) -> AsyncSession:
    """
    Igual que get_db pero OBLIGA a enviar una residencia (header o query), salvo superadmin.
    Valida pertenencia y fija app.residence_id.
    """
    residence_id = residence_id_header or residence_id_query

    if current["role"] != "superadmin" and not residence_id:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
        )

    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": current["id"]})

        if residence_id:
            ok = await session.execute(
                select(UserResidence).where(
                    UserResidence.user_id == current["id"],
                    UserResidence.residence_id == residence_id,
                )
            )
            if current["role"] != "superadmin" and ok.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail="Residence not allowed for this user")

            await session.execute(text("SELECT set_config('app.residence_id', :rid, true)"), {"rid": residence_id})

        yield session