from sqlalchemy import Column, Integer, String, Date, Enum, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime

class GenderEnum(enum.Enum):
    masculino = "masculino"
    femenino = "femenino"
    otro = "otro"

class UserRoleEnum(enum.Enum):
    candidato = "candidato"
    empresa = "empresa"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRoleEnum), nullable=False)
    verified = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=True, nullable=False)

    # Campos comunes
    nombre = Column(String, nullable=False)
    profile_picture = Column(String, nullable=True)

    # Campos específicos de candidatos (nullable para empresas y admin)
    apellido = Column(String, nullable=True)
    genero = Column(Enum(GenderEnum), nullable=True)
    fecha_nacimiento = Column(Date, nullable=True)

    # Campos específicos de empresas (nullable para candidatos y admin)
    descripcion = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones para recruiters
    recruiting_for = relationship("CompanyRecruiter", foreign_keys="CompanyRecruiter.recruiter_id", back_populates="recruiter")
    company_recruiters = relationship("CompanyRecruiter", foreign_keys="CompanyRecruiter.company_id", back_populates="company")

class CompanyRecruiter(Base):
    __tablename__ = "company_recruiters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relaciones
    company = relationship("User", foreign_keys=[company_id], back_populates="company_recruiters")
    recruiter = relationship("User", foreign_keys=[recruiter_id], back_populates="recruiting_for")
