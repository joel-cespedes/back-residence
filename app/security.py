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

def encrypt_data(data: str) -> bytes:
    """
    Encripta datos sensibles usando Fernet.
    """
    if not data:
        return b''
    # Por ahora, codificar directamente como UTF-8 para compatibilidad
    # TODO: Implementar Fernet encryption cuando se genere la clave
    return data.encode('utf-8')

def decrypt_data(encrypted_data: bytes) -> str:
    """
    Desencripta datos sensibles.
    """
    if not encrypted_data:
        return ''
    # Por ahora, decodificar directamente como UTF-8 para compatibilidad
    # TODO: Implementar Fernet decryption cuando se genere la clave
    try:
        return encrypted_data.decode('utf-8')
    except (UnicodeDecodeError, AttributeError):
        return str(encrypted_data)
