# =====================================================================
# MÓDULO DE MODELOS DE BASE DE DATOS
# =====================================================================

"""
Módulo que contiene todos los modelos de la base de datos del sistema de residencias.
Cada modelo está separado en su propio archivo por entidad.
"""

# Importar la clase base y enumeraciones
from .base import Base, user_role_enum, resident_status_enum, device_type_enum, measurement_type_enum, measurement_source_enum

# Importar modelos por entidad
from .user import User
from .residence import Residence, UserResidence
from .location import Floor, Room, Bed
from .resident import Resident
from .device import Device
from .task import TaskCategory, TaskTemplate, TaskApplication
from .measurement import Measurement
from .tag import Tag, ResidentTag
from .event import EventLog

# Exportar todos los modelos para fácil importación
__all__ = [
    # Base y enums
    "Base",
    "user_role_enum",
    "resident_status_enum",
    "device_type_enum",
    "measurement_type_enum",
    "measurement_source_enum",

    # Modelos principales
    "User",
    "Residence",
    "UserResidence",
    "Floor",
    "Room",
    "Bed",
    "Resident",
    "Device",
    "TaskCategory",
    "TaskTemplate",
    "TaskApplication",
    "Measurement",
    "Tag",
    "ResidentTag",
    "EventLog",
]