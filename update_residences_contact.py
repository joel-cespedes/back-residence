#!/usr/bin/env python3
"""
Script para actualizar las residencias existentes con datos de contacto y fechas aleatorias
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import List
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from app.models import Base, Residence
from app.config import settings

# Configuración de la base de datos
engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Datos de contacto para residencias
DATOS_CONTACTO_RESIDENCIAS = [
    ("+34 91 123 45 67", "info@residenciasantaclara.com"),
    ("+34 91 234 56 78", "contacto@residenciarosal.com"),
    ("+34 91 345 67 89", "admin@residencialaesperanza.com"),
    ("+34 91 456 78 90", "info@residenciasanjose.com"),
    ("+34 91 567 89 01", "contacto@residencialosolivos.com"),
    ("+34 91 678 90 12", "admin@residencialapaz.com"),
    ("+34 91 789 01 23", "info@residenciaelroble.com"),
    ("+34 91 890 12 34", "contacto@residencialafloresta.com"),
    ("+34 91 901 23 45", "admin@residenciasanjuan.com"),
    ("+34 91 012 34 56", "info@residenciaelmirador.com"),
    ("+34 91 123 45 67", "contacto@residenciaalameda.com"),
    ("+34 91 234 56 78", "admin@residencialasacacias.com"),
    ("+34 91 345 67 89", "info@residenciaelprado.com"),
    ("+34 91 456 78 90", "contacto@residencialacolina.com"),
    ("+34 91 567 89 01", "admin@residenciasanfrancisco.com"),
    ("+34 91 678 90 12", "info@residenciaelbosque.com"),
    ("+34 91 789 01 23", "contacto@residencialaroca.com"),
    ("+34 91 890 12 34", "admin@residenciaellago.com"),
    ("+34 91 901 23 45", "info@residenciasanantonio.com"),
    ("+34 91 012 34 56", "contacto@residencialamontana.com"),
    ("+34 91 123 45 67", "admin@residenciaeljardin.com"),
    ("+34 91 234 56 78", "info@residencialacima.com"),
    ("+34 91 345 67 89", "contacto@residenciasanpedro.com"),
    ("+34 91 456 78 90", "admin@residenciaelvalle.com"),
    ("+34 91 567 89 01", "info@residencialafuente.com"),
    ("+34 91 678 90 12", "contacto@residenciaelsol.com"),
    ("+34 91 789 01 23", "admin@residenciasanmiguel.com"),
    ("+34 91 890 12 34", "info@residencialaluna.com")
]

class ResidenceUpdater:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def update_residences_with_contact_data(self):
        """Actualiza las residencias existentes con datos de contacto y fechas aleatorias"""
        print("🏠 Actualizando residencias con datos de contacto...")

        # Obtener todas las residencias existentes
        result = await self.session.execute(
            select(Residence).where(Residence.deleted_at.is_(None))
        )
        residences = result.scalars().all()

        print(f"📊 Encontradas {len(residences)} residencias")

        for i, residence in enumerate(residences):
            # Obtener datos de contacto para esta residencia
            phone, email = DATOS_CONTACTO_RESIDENCIAS[i % len(DATOS_CONTACTO_RESIDENCIAS)]

            # Generar fecha de creación aleatoria en los últimos 2 años
            days_ago = random.randint(0, 730)  # 0 a 730 días atrás
            created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

            # Generar fecha de actualización aleatoria entre la creación y ahora
            updated_at = created_at + timedelta(days=random.randint(0, days_ago))

            # Actualizar residencia
            residence.phone_encrypted = phone.encode('utf-8')
            residence.email_encrypted = email.encode('utf-8')
            residence.created_at = created_at
            residence.updated_at = updated_at

            print(f"  📝 Actualizando {residence.name}: {phone}, {email}, creada el {created_at.strftime('%Y-%m-%d')}")

        # Guardar cambios
        await self.session.commit()
        print("✅ Residencias actualizadas exitosamente!")
        print(f"📊 Total de residencias actualizadas: {len(residences)}")


async def main():
    """Función principal"""
    async with async_session() as session:
        updater = ResidenceUpdater(session)
        await updater.update_residences_with_contact_data()


if __name__ == "__main__":
    asyncio.run(main())