# app/db.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.config import settings

# Crea el engine async (Postgres). La URL viene de .env (DATABASE_URL)
# Ejemplo válido:
#   postgresql+asyncpg://user:pass@localhost:5432/residences   (asyncpg)
#   postgresql+psycopg://user:pass@localhost:5432/residences   (psycopg2)
# Si la URL no tiene prefijo, intentamos usar asyncpg por defecto
database_url = settings.database_url
if not database_url.startswith(('postgresql+asyncpg://', 'postgresql+psycopg://')):
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    elif database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+asyncpg://', 1)

engine = create_async_engine(
    database_url,
    future=True,
    pool_pre_ping=True,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_session(user_id: str | None):
    """
    Devuelve una sesión configurando app.user_id para RLS/auditoría.
    Úsala en endpoints que requieren usuario autenticado.
    """
    async with AsyncSessionLocal() as session:
        uid = user_id or ""
        # Fija el user_id de la petición para las políticas RLS en Postgres
        await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": uid})
        yield session

async def get_session_anon():
    """
    Devuelve una sesión 'anónima' (app.user_id = '').
    Útil para /auth/login (no hay usuario aún).
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT set_config('app.user_id', '', true)"))
        yield session
