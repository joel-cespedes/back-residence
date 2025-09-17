# =====================================================================
# ESQUEMAS DE AUTENTICACIÓN
# =====================================================================

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel

# =========================================================
# ESQUEMAS DE AUTENTICACIÓN
# =========================================================

class LoginRequest(BaseModel):
    """
    Esquema para la solicitud de inicio de sesión.

    Attributes:
        alias (str): Alias o nombre de usuario del usuario
        password (str): Contraseña del usuario (en texto plano)
    """
    alias: str
    password: str


class TokenResponse(BaseModel):
    """
    Esquema para la respuesta del token de acceso.

    Attributes:
        access_token (str): Token JWT de acceso
        token_type (Literal["bearer"]): Tipo de token (siempre 'bearer')
    """
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class Me(BaseModel):
    """
    Esquema para la información básica del usuario actual.

    Attributes:
        id (str): Identificador único del usuario
        role (str): Rol del usuario en el sistema
        alias (str): Alias o nombre de usuario del usuario
    """
    id: str
    role: str
    alias: str | None = None