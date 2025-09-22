from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Base schema
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: str = 'user'
    is_active: bool = True

# Schema para creación
class UserCreate(UserBase):
    password: str

# Schema para actualización
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

# Schema para respuesta
class User(UserBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    residence_ids: List[int] = []
    residence_names: List[str] = []
    residence_count: int = 0

    class Config:
        from_attributes = True

# Schema para residencia simple
class ResidenceSimple(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

# Schema para paginación
class PaginatedUsersResponse(BaseModel):
    items: List[User]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool

# Schema para asignación de residencias
class ResidenceAssignment(BaseModel):
    residence_ids: List[int]