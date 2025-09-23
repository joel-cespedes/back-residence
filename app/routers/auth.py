# app/routers/auth.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import LoginRequest, TokenResponse
from app.models import User
from app.security import hash_alias, verify_password, create_access_token
from app.db import get_session_anon

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_session_anon),
):
    # NO transaction context here: the SET CONFIG in dependency already started one
    q = await session.execute(
        select(User).where(User.alias_hash == hash_alias(data.alias))
    )
    user = q.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(sub=str(user.id), role=user.role, alias=data.alias)
    return TokenResponse(access_token=token)

