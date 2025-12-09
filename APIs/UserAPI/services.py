"""
UserService - Versión Simplificada Final

Funcionalidades:
- Autenticación (login)
- Registro (candidatos y empresas)
- Consultas de usuarios
- Actualización de perfil
- Funciones admin básicas
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile
from typing import List, Optional, TYPE_CHECKING
import os
import uuid
import re

if TYPE_CHECKING:
    from models import User
    from schemas import CandidatoCreate, EmpresaCreate, UserUpdate

from models import UserRoleEnum, GenderEnum
from auth import get_password_hash, verify_password


class UserService:
    """Servicio para gestión de usuarios"""

    def __init__(self, db: Session):
        self.db = db

    # =====================================================
    # FUNCIONES DE CONSULTA
    # =====================================================

    def get_user_by_email(self, email: str) -> Optional['User']:
        """Obtiene un usuario por email"""
        from models import User
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional['User']:
        """Obtiene un usuario por ID"""
        from models import User
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all_users(self, skip: int = 0, limit: int = 100) -> List['User']:
        """Obtiene todos los usuarios (endpoint admin)"""
        from models import User
        return self.db.query(User).offset(skip).limit(limit).all()

    def get_all_candidates(self, skip: int = 0, limit: int = 100) -> List['User']:
        """Obtiene todos los candidatos (endpoint admin)"""
        from models import User
        return self.db.query(User).filter(
            User.role == UserRoleEnum.candidato
        ).offset(skip).limit(limit).all()

    # =====================================================
    # AUTENTICACIÓN
    # =====================================================

    def authenticate_user(self, email: str, password: str) -> Optional['User']:
        """
        Autentica un usuario con email y contraseña

        Args:
            email: Email del usuario
            password: Contraseña en texto plano

        Returns:
            User si las credenciales son válidas, None en caso contrario
        """
        # Truncar contraseña a 72 bytes (límite bcrypt)
        password_bytes = password.encode('utf-8')[:72]
        password_truncated = password_bytes.decode('utf-8', errors='ignore')

        user = self.get_user_by_email(email)
        if not user:
            return None

        if not verify_password(password_truncated, user.hashed_password):
            return None

        return user

    # =====================================================
    # REGISTRO
    # =====================================================

    def create_candidato_simple(
        self,
        candidato_data: 'CandidatoCreate',
        profile_picture: Optional[UploadFile] = None
    ) -> 'User':
        """
        Crea un candidato directamente sin verificación de email

        Args:
            candidato_data: Datos del candidato (CandidatoCreate schema)
            profile_picture: Foto de perfil opcional

        Returns:
            User creado

        Raises:
            HTTPException: Si el email ya existe
        """
        from models import User

        # Verificar que el email no exista
        existing_user = self.get_user_by_email(candidato_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El email {candidato_data.email} ya está registrado"
            )

        # Truncar contraseña a 72 bytes (límite bcrypt)
        password_bytes = candidato_data.password.encode('utf-8')[:72]
        password_truncated = password_bytes.decode('utf-8', errors='ignore')

        # Guardar foto de perfil si existe
        profile_pic_filename = None
        if profile_picture and profile_picture.filename:
            profile_pic_filename = self._save_profile_picture(profile_picture, candidato_data.email)

        # Crear usuario directamente
        new_user = User(
            email=candidato_data.email,
            hashed_password=get_password_hash(password_truncated),
            nombre=candidato_data.nombre,
            apellido=candidato_data.apellido,
            genero=candidato_data.genero,
            fecha_nacimiento=candidato_data.fecha_nacimiento,
            role=UserRoleEnum.candidato,
            verified=True,
            email_verified=True,
            profile_picture=profile_pic_filename
        )

        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)

        return new_user

    def create_empresa_simple(
        self,
        empresa_data: 'EmpresaCreate',
        profile_picture: Optional[UploadFile] = None
    ) -> 'User':
        """
        Crea una empresa directamente sin verificación de email

        Args:
            empresa_data: Datos de la empresa (EmpresaCreate schema)
            profile_picture: Logo de la empresa opcional

        Returns:
            User creado con rol EMPRESA

        Raises:
            HTTPException: Si el email ya existe
        """
        from models import User

        # Verificar que el email no exista
        existing_user = self.get_user_by_email(empresa_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El email {empresa_data.email} ya está registrado"
            )

        # Truncar contraseña a 72 bytes (límite bcrypt)
        password_bytes = empresa_data.password.encode('utf-8')[:72]
        password_truncated = password_bytes.decode('utf-8', errors='ignore')

        # Guardar logo si existe
        profile_pic_filename = None
        if profile_picture and profile_picture.filename:
            profile_pic_filename = self._save_profile_picture(profile_picture, empresa_data.email)

        # Crear empresa directamente
        new_user = User(
            email=empresa_data.email,
            hashed_password=get_password_hash(password_truncated),
            nombre=empresa_data.nombre,
            descripcion=empresa_data.descripcion,
            role=UserRoleEnum.empresa,
            verified=True,
            email_verified=True,
            profile_picture=profile_pic_filename
        )

        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)

        return new_user

    # =====================================================
    # ACTUALIZACIÓN DE PERFIL
    # =====================================================

    def update_user(
        self,
        user_id: int,
        user_update: 'UserUpdate',
        profile_picture: Optional[UploadFile] = None
    ) -> 'User':
        """
        Actualiza el perfil de un usuario

        Args:
            user_id: ID del usuario a actualizar
            user_update: Datos a actualizar (UserUpdate schema)
            profile_picture: Nueva foto de perfil opcional

        Returns:
            User actualizado

        Raises:
            HTTPException: Si el usuario no existe
        """
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # Actualizar campos básicos
        update_data = user_update.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field != "password" and hasattr(user, field) and value is not None:
                setattr(user, field, value)

        # Actualizar contraseña si se proporciona
        if hasattr(user_update, 'password') and user_update.password:
            password_bytes = user_update.password.encode('utf-8')[:72]
            password_truncated = password_bytes.decode('utf-8', errors='ignore')
            user.hashed_password = get_password_hash(password_truncated)

        # Actualizar foto de perfil si se proporciona
        if profile_picture and profile_picture.filename and profile_picture.size > 0:
            profile_pic_filename = self._save_profile_picture(profile_picture, user.email)
            user.profile_picture = profile_pic_filename

        self.db.commit()
        self.db.refresh(user)

        return user

    # =====================================================
    # FUNCIONES AUXILIARES PRIVADAS
    # =====================================================

    def _save_profile_picture(self, picture_file: UploadFile, email: str) -> str:
        """
        Guarda una foto de perfil en el sistema de archivos (seguro contra path injection)

        Args:
            picture_file: Archivo de imagen
            email: Email del usuario (para nombrar el archivo)

        Returns:
            Nombre del archivo guardado
        """
        # Crear directorio si no existe
        base_dir = "profile_pictures"
        os.makedirs(base_dir, exist_ok=True)

        # Whitelist de extensiones permitidas (seguridad)
        ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

        # Sanitizar extensión del archivo
        if picture_file.filename and '.' in picture_file.filename:
            extension = picture_file.filename.rsplit('.', 1)[1].lower()
            # Validar extensión contra whitelist
            if extension not in ALLOWED_EXTENSIONS:
                extension = 'jpg'  # Default seguro
        else:
            extension = 'jpg'

        # Sanitizar email: solo alfanuméricos, guiones y underscores
        safe_email = re.sub(r'[^a-zA-Z0-9_-]', '_', email.split('@')[0])

        # Generar nombre único y seguro
        filename = f"{safe_email}_{uuid.uuid4().hex[:8]}.{extension}"

        # Construir path y validar que está dentro del directorio base
        filepath = os.path.join(base_dir, filename)
        # Resolver path absoluto y verificar que está dentro de base_dir
        abs_base = os.path.abspath(base_dir)
        abs_filepath = os.path.abspath(filepath)
        if not abs_filepath.startswith(abs_base + os.sep):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path"
            )

        # Guardar archivo
        with open(filepath, "wb") as f:
            content = picture_file.file.read()
            f.write(content)

        return filename
