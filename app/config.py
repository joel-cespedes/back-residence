from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/residences")
    jwt_secret: str = os.getenv("JWT_SECRET", "change_me_please")
    jwt_alg: str = os.getenv("JWT_ALG", "HS256")
    alias_hash_alg: str = os.getenv("ALIAS_HASH_ALG", "sha256")
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

settings = Settings()



