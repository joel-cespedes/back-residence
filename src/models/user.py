from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

# Tabla de muchos a muchos entre usuarios y residencias
user_residence = Table(
    'user_residence',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('residence_id', Integer, ForeignKey('residences.id'), primary_key=True)
)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='user')  # 'user', 'manager', 'admin', 'superadmin'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_login = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Relaciones
    created_by_user = relationship("User", remote_side=[id], foreign_keys=[created_by])
    residences = relationship("Residence", secondary=user_residence, back_populates="users")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


class Residence(Base):
    __tablename__ = 'residences'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    address = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    # Relaciones
    users = relationship("User", secondary=user_residence, back_populates="residences")

    def __repr__(self):
        return f"<Residence(id={self.id}, name={self.name})>"