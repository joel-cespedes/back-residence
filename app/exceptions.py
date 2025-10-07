from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Solo loguear como ERROR si es un error del servidor (5xx)
        if exc.status_code >= 500:
            logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
        elif exc.status_code >= 400:
            # Errores de cliente (4xx) son WARNING o INFO
            logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.detail,
                "type": "http_error"
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Errores de validación son errores del cliente, no del servidor
        logger.warning(f"Validation Error: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "message": "Error de validación en los datos enviados",
                "type": "validation_error",
                "details": exc.errors()
            }
        )

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        # Manejar errores de integridad de la base de datos
        error_message = str(exc.orig).lower() if hasattr(exc, 'orig') else str(exc)

        # Mapear errores comunes de unique constraint
        if "unique constraint" in error_message or "duplicate key" in error_message:
            # Extraer el nombre de la constraint si está disponible
            constraint_name = ""
            if "uq_" in error_message:
                # Buscar el nombre de la constraint
                import re
                match = re.search(r'constraint["\']([^"\']+)["\']', error_message)
                if match:
                    constraint_name = match.group(1)

            # Mensajes más amigables según la constraint
            if "residence_name" in constraint_name:
                message = "Ya existe una residencia con ese nombre"
            elif "floor_residence_name" in constraint_name:
                message = "Ya existe un piso con ese nombre en esta residencia"
            elif "room_floor_name" in constraint_name:
                message = "Ya existe una habitación con ese nombre en este piso"
            elif "bed_room_name" in constraint_name:
                message = "Ya existe una cama con ese nombre en esta habitación"
            elif "device_residence_name" in constraint_name:
                message = "Ya existe un dispositivo con ese nombre en esta residencia"
            elif "tag_residence_name" in constraint_name:
                message = "Ya existe una etiqueta con ese nombre en esta residencia"
            else:
                message = "Ya existe un registro con esos datos únicos"

        elif "foreign key constraint" in error_message:
            message = "No se puede eliminar/actualizar este registro porque está siendo referenciado por otros registros"

        elif "not-null constraint" in error_message:
            message = "Faltan campos obligatorios"

        else:
            message = "Error de integridad en la base de datos"

        logger.error(f"Database Integrity Error: {error_message}")
        return JSONResponse(
            status_code=400,
            content={
                "error": True,
                "message": message,
                "type": "integrity_error",
                "constraint": constraint_name if "constraint" in locals() else None
            }
        )

    @app.exception_handler(DBAPIError)
    async def db_exception_handler(request: Request, exc: DBAPIError):
        logger.error(f"Database Error: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "Error en la base de datos",
                "type": "database_error"
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unexpected Error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "Error interno del servidor",
                "type": "internal_error"
            }
        )