#!/usr/bin/env python3
"""
Script para crear las tablas de la base de datos
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import Base
from app.config import settings

async def main():
    """Crear todas las tablas en la base de datos"""
    engine = create_async_engine(settings.database_url, echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("✅ Tablas creadas exitosamente")

if __name__ == "__main__":
    asyncio.run(main())