import hashlib, jwt, datetime, bcrypt
import uuid
from app.config import settings

def new_uuid() -> str:
    """UUID v4 como string (compatible con columnas UUID-as-text)."""
    return str(uuid.uuid4())

def normalize_alias(alias: str) -> str:
    return alias.strip().lower()

def hash_alias(alias: str) -> str:
    h = hashlib.new(settings.alias_hash_alg)
    h.update(normalize_alias(alias).encode("utf-8"))
    return h.hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    # hashed es bcrypt (formato $2a$...) compatible con bcrypt.checkpw
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(sub: str, role: str, expires_minutes: int = 120, alias: str = None) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=expires_minutes),
        "typ": "access",
    }
    if alias:
        payload["alias"] = alias
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])

def decrypt_data(encrypted_data: bytes) -> str:
    """
    Función temporal para 'desencriptar' datos.
    NOTA: Actualmente los datos no están realmente encriptados, solo hasheados.
    Esto debería implementarse con una encriptación real como Fernet.
    """
    try:
        # Por ahora, intentar decodificar como UTF-8 si es un hash
        return encrypted_data.decode('utf-8')
    except (UnicodeDecodeError, AttributeError):
        # Si falla, devolver una representación segura
        return str(encrypted_data)
