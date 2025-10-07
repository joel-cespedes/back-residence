# app/logging_config.py
"""
Configuración de logging estructurado (JSON) para producción.
Facilita búsqueda y análisis de logs en herramientas como CloudWatch, Datadog, etc.
"""

import logging
import sys
from pythonjsonlogger import jsonlogger


def setup_logging():
    """Configura logging estructurado en formato JSON"""

    # Crear handler para stdout
    logHandler = logging.StreamHandler(sys.stdout)

    # Formato JSON con campos útiles
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )

    logHandler.setFormatter(formatter)

    # Configurar logger raíz
    logger = logging.getLogger()
    logger.addHandler(logHandler)
    logger.setLevel(logging.INFO)

    # Reducir verbosidad de librerías externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    return logger


# Logger global
logger = setup_logging()
