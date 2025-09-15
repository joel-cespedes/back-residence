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

def create_access_token(sub: str, role: str, expires_minutes: int = 120) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=expires_minutes),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
