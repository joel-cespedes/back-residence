# =====================================================================
# ENUMERACIONES DEL SISTEMA
# =====================================================================

from __future__ import annotations

from typing import Literal

# =========================================================
# ENUMERACIONES PRINCIPALES
# =========================================================

"""
Enumeraciones principales que definen los tipos y estados del sistema.
Estas enumeraciones deben coincidir con las definiciones en la base de datos.
"""

# Roles de usuario en el sistema
UserRole = Literal["superadmin", "manager", "professional"]

# Estados posibles de un residente
ResidentStatus = Literal["active", "discharged", "deceased"]

# Tipos de dispositivos médicos disponibles
DeviceType = Literal["blood_pressure", "pulse_oximeter", "scale", "thermometer"]

# Fuentes posibles para las mediciones
MeasurementSource = Literal["device", "voice", "manual"]

# Tipos de mediciones médicas soportadas
MeasurementType = Literal["bp", "spo2", "weight", "temperature"]