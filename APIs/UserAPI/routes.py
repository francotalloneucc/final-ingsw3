from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Header, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta, date
import os
import httpx

from database import get_db
from schemas import UserResponse, CandidatoCreate, EmpresaCreate, UserUpdate, Token, UserLogin, CompanyVerification
from services import UserService
from auth import create_access_token, get_current_user, get_current_user_optional, ACCESS_TOKEN_EXPIRE_MINUTES
from models import User, GenderEnum, UserRoleEnum, CompanyRecruiter

router = APIRouter()
security = HTTPBearer()

# 🔒 SEGURIDAD: API Key para comunicación interna entre servicios
INTERNAL_API_KEY = os.getenv("INTERNAL_SERVICE_API_KEY", "internal-service-key-change-in-production")

def verify_internal_api_key(x_internal_api_key: Optional[str] = Header(None)):
    """Verifica que la API key interna sea válida para comunicación entre servicios"""
    if x_internal_api_key is None or x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="API key interna inválida o faltante"
        )
    return True

# ⭐ ENDPOINT SIMPLIFICADO - Registro directo de candidatos (sin CV ni verificación)
@router.post("/register-candidato", response_model=UserResponse)
async def register_candidato(
    email: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    genero: GenderEnum = Form(...),
    fecha_nacimiento: date = Form(...),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Registra candidato directamente - sin CV ni verificación de email"""
    candidato_create = CandidatoCreate(
        email=email,
        password=password,
        nombre=nombre,
        apellido=apellido,
        genero=genero,
        fecha_nacimiento=fecha_nacimiento
    )

    user_service = UserService(db)
    # Crear candidato directamente sin verificación
    user = user_service.create_candidato_simple(candidato_create, profile_picture)
    return user

# ⭐ ENDPOINT SIMPLIFICADO - Registro directo de empresas (sin verificación)
@router.post("/register-empresa", response_model=UserResponse)
async def register_empresa(
    email: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
    descripcion: str = Form(...),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Registra empresa directamente - sin verificación de email"""
    empresa_create = EmpresaCreate(
        email=email,
        password=password,
        nombre=nombre,
        descripcion=descripcion
    )

    user_service = UserService(db)
    # Crear empresa directamente sin verificación
    user = user_service.create_empresa_simple(empresa_create, profile_picture)
    return user

# 🆕 ENDPOINT PROXY - Analizar CV (para uso del frontend durante registro)
@router.post("/analyze-cv")
async def analyze_cv_proxy(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Endpoint proxy para analizar CVs. El frontend llama a este endpoint
    y UserAPI se encarga de comunicarse con CvAnalyzerAPI con el API key correcto.
    """
    user_service = UserService(db)

    # Usar el método existente que ya maneja el API key
    result = user_service.analyze_cv_with_api(file)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es un CV válido o no se pudo analizar"
        )

    return {
        "valid": True,
        "data": result
    }

# ⭐ ENDPOINT UNIFICADO - Completar cualquier tipo de registro
@router.post("/complete-registration", response_model=UserResponse)
async def complete_registration(
    email: str = Form(...),
    verification_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Completa el registro después de verificar el email (candidato o empresa)"""
    user_service = UserService(db)
    
    # Obtener datos temporales para determinar el tipo
    temp_data = user_service.temp_storage.get_pending_registration(email)
    if not temp_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontraron datos de registro pendientes para este email"
        )
    
    user_type = temp_data["registration_data"].get("user_type")
    
    if user_type == "candidato":
        user = user_service.complete_candidato_registration(email, verification_code)
    elif user_type == "empresa":
        user = user_service.complete_empresa_registration(email, verification_code)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de usuario no válido en los datos temporales"
        )
    
    return user

# ⭐ ENDPOINT ESPECÍFICO - Completar registro de candidato
@router.post("/complete-candidato-registration", response_model=UserResponse)
async def complete_candidato_registration(
    email: str = Form(...),
    verification_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Completa el registro del candidato después de verificar el email"""
    user_service = UserService(db)
    user = user_service.complete_candidato_registration(email, verification_code)
    return user

# ⭐ ENDPOINT ESPECÍFICO - Completar registro de empresa
@router.post("/complete-empresa-registration", response_model=UserResponse)
async def complete_empresa_registration(
    email: str = Form(...),
    verification_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Completa el registro de empresa después de verificar el email"""
    user_service = UserService(db)
    user = user_service.complete_empresa_registration(email, verification_code)
    return user

# ⭐ ENDPOINT OBSOLETO - DESHABILITADO
@router.post("/register", response_model=dict)
async def register_user(
    email: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    genero: GenderEnum = Form(...),
    fecha_nacimiento: date = Form(...),
    cv_file: UploadFile = File(...),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """DESHABILITADO: Usar /register-candidato + /complete-registration"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Este endpoint está deshabilitado. Usar /register-candidato seguido de /complete-registration"
    )

# ⭐ ENDPOINT ACTUALIZADO - Verificar email (funciona con storage temporal)
@router.post("/verify-email")
async def verify_email(
    email: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verifica código de email (solo validación, no completa registro)"""
    user_service = UserService(db)
    success = user_service.verify_email_code(email, code)
    
    if success:
        return {"message": "Código verificado correctamente", "success": True}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido o expirado"
        )

# Endpoint para reenviar código de verificación con cooldown
@router.post("/resend-verification")
async def resend_verification(
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Reenvía código de verificación con cooldown de 2 minutos entre reenvíos"""
    user_service = UserService(db)
    result = user_service.resend_verification_code(email)

    if result["success"]:
        return {
            "message": result["message"],
            "success": True,
            "cooldown_seconds": result.get("cooldown_seconds", 120)
        }
    else:
        # Si hay cooldown activo, devolver 429 (Too Many Requests)
        if "seconds_remaining" in result:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=result["message"],
                headers={"Retry-After": str(result["seconds_remaining"])}
            )
        # Otro error (no existe registro, etc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )

# ⭐ ENDPOINT ACTUALIZADO - Login con validación de email verificado
@router.post("/login", response_model=Token)
async def login_user(user_login: UserLogin, db: Session = Depends(get_db)):
    user_service = UserService(db)
    user = user_service.authenticate_user(user_login.email, user_login.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # ⭐ NUEVO: Verificar que el email esté verificado
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu email antes de iniciar sesión. Revisa tu bandeja de entrada.",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint para obtener el usuario actual
@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

# Endpoint para obtener todos los usuarios
@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_service = UserService(db)
    return user_service.get_all_users(skip=skip, limit=limit)

# ⭐ ENDPOINT CORREGIDO - Datos básicos públicos, datos completos solo con autenticación
@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Obtener información de usuario.
    - Público: solo nombre, id, rol
    - Autenticado: datos completos si es el dueño o admin
    """
    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # 🔒 SEGURIDAD: Si no está autenticado, devolver solo datos públicos mínimos
    if current_user is None:
        return UserResponse(
            id=user.id,
            nombre=user.nombre,
            apellido=user.apellido if user.role == UserRoleEnum.candidato else None,
            role=user.role,
            # Resto de campos en None por seguridad
            email=None,
            fecha_nacimiento=None,
            verified=None,
            profile_picture=user.profile_picture,  # Foto pública
            cv_filename=None,  # NO exponer filename
            cv_analizado=None,  # NO exponer datos del CV
            descripcion=user.descripcion if user.role == UserRoleEnum.empresa else None,
            created_at=None
        )

    # 🔒 SEGURIDAD: Si está autenticado, verificar permisos
    is_owner = current_user.id == user_id
    is_admin = current_user.role == UserRoleEnum.admin

    # Datos completos solo para el dueño o admin
    if is_owner or is_admin:
        return UserResponse(
            id=user.id,
            email=user.email,
            nombre=user.nombre,
            apellido=user.apellido,
            fecha_nacimiento=user.fecha_nacimiento,
            role=user.role,
            verified=user.verified,
            profile_picture=user.profile_picture,
            cv_filename=user.cv_filename,
            cv_analizado=user.cv_analizado,
            descripcion=user.descripcion,
            created_at=user.created_at
        )
    else:
        # Usuario autenticado pero no es el dueño: datos públicos limitados
        return UserResponse(
            id=user.id,
            nombre=user.nombre,
            apellido=user.apellido if user.role == UserRoleEnum.candidato else None,
            role=user.role,
            email=None,
            fecha_nacimiento=None,
            verified=user.verified if user.role == UserRoleEnum.empresa else None,
            profile_picture=user.profile_picture,
            cv_filename=None,
            cv_analizado=None,
            descripcion=user.descripcion if user.role == UserRoleEnum.empresa else None,
            created_at=None
        )

# 🔒 ENDPOINT INTERNO - Para comunicación entre servicios (JobsAPI, MatcheoAPI, etc.)
@router.get("/internal/users/{user_id}", response_model=UserResponse)
async def get_user_internal(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_internal_api_key)
):
    """
    Endpoint interno para que otros servicios obtengan datos completos de usuarios.
    Requiere API key interna en header X-Internal-API-Key.
    Solo para uso de JobsAPI, MatcheoAPI, etc.
    """
    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Devolver datos completos para servicios internos
    return UserResponse(
        id=user.id,
        email=user.email,
        nombre=user.nombre,
        apellido=user.apellido,
        fecha_nacimiento=user.fecha_nacimiento,
        role=user.role,
        verified=user.verified,
        profile_picture=user.profile_picture,
        cv_filename=user.cv_filename,
        cv_analizado=user.cv_analizado,
        descripcion=user.descripcion,
        created_at=user.created_at
    )

# Endpoint para actualizar usuario
@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    email: str = Form(None),
    password: str = Form(None),
    nombre: str = Form(None),
    apellido: str = Form(None),
    genero: GenderEnum = Form(None),
    fecha_nacimiento: date = Form(None),
    cv_file: UploadFile = File(None),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 🔒 SEGURIDAD: Verificar que el usuario solo pueda actualizar su propia cuenta (o sea admin)
    if current_user.id != user_id and current_user.role != UserRoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para actualizar esta cuenta"
        )

    user_update = UserUpdate(
        email=email,
        password=password,
        nombre=nombre,
        apellido=apellido,
        genero=genero,
        fecha_nacimiento=fecha_nacimiento
    )

    user_service = UserService(db)
    return user_service.update_user(user_id, user_update, cv_file, profile_picture)

# Endpoint para eliminar usuario
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 🔒 SEGURIDAD: Verificar que el usuario solo pueda eliminar su propia cuenta (o sea admin)
    if current_user.id != user_id and current_user.role != UserRoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para eliminar esta cuenta"
        )

    user_service = UserService(db)
    user_service.delete_user(user_id)
    return {"message": "Usuario eliminado exitosamente"}

# Endpoint para actualizar candidato actual
@router.put("/me/candidato", response_model=UserResponse)
async def update_current_candidato(
    nombre: str = Form(None),
    apellido: str = Form(None),
    genero: GenderEnum = Form(None),
    fecha_nacimiento: date = Form(None),
    cv_file: UploadFile = File(None),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar que sea un candidato
    if current_user.role != UserRoleEnum.candidato:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo candidatos pueden usar este endpoint"
        )
    
    user_update = UserUpdate()
    if nombre is not None:
        user_update.nombre = nombre
    if apellido is not None:
        user_update.apellido = apellido
    if genero is not None:
        user_update.genero = genero
    if fecha_nacimiento is not None:
        user_update.fecha_nacimiento = fecha_nacimiento
    
    user_service = UserService(db)
    return user_service.update_user(current_user.id, user_update, cv_file, profile_picture)

# Endpoint para actualizar empresa actual
@router.put("/me/empresa", response_model=UserResponse)
async def update_current_empresa(
    nombre: str = Form(None),
    descripcion: str = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar que sea una empresa
    if current_user.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empresas pueden usar este endpoint"
        )
    
    user_update = UserUpdate()
    if nombre is not None:
        user_update.nombre = nombre
    if descripcion is not None:
        user_update.descripcion = descripcion
    
    user_service = UserService(db)
    return user_service.update_user(current_user.id, user_update, None, profile_picture)

# Endpoint genérico (mantener para compatibilidad - decide automáticamente)
@router.put("/me", response_model=UserResponse)
async def update_current_user(
    # Campos comunes
    nombre: str = Form(None),
    
    # Campos específicos de candidatos
    apellido: str = Form(None),
    genero: GenderEnum = Form(None),
    fecha_nacimiento: date = Form(None),
    cv_file: UploadFile = File(None),
    
    # Campos específicos de empresas
    descripcion: str = Form(None),
    
    # Campo común para todos
    profile_picture: Optional[UploadFile] = File(None),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Crear user_update dinámicamente según el rol del usuario
    user_update = UserUpdate()
    
    # Campo común para todos los roles
    if nombre is not None:
        user_update.nombre = nombre
    
    # Solo procesar campos específicos según el rol del usuario actual
    if current_user.role == UserRoleEnum.candidato:
        # Solo candidatos pueden actualizar estos campos
        if apellido is not None:
            user_update.apellido = apellido
        if genero is not None:
            user_update.genero = genero
        if fecha_nacimiento is not None:
            user_update.fecha_nacimiento = fecha_nacimiento
    
    elif current_user.role == UserRoleEnum.empresa:
        # Solo empresas pueden actualizar descripción
        if descripcion is not None:
            user_update.descripcion = descripcion
    
    user_service = UserService(db)
    return user_service.update_user(current_user.id, user_update, cv_file, profile_picture)

# Función para verificar si es admin
def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requieren permisos de administrador"
        )
    return current_user

# Endpoints para administradores
@router.get("/admin/companies/pending", response_model=List[UserResponse])
async def get_pending_companies(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Ver empresas pendientes de verificación"""
    user_service = UserService(db)
    return user_service.get_unverified_companies()

# Endpoint simple para verificar empresa (solo email)
@router.post("/admin/companies/verify")
async def verify_company_simple(
    company_email: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Verificar empresa por email (endpoint simple)"""
    user_service = UserService(db)
    
    # Buscar empresa por email
    company = user_service.get_user_by_email(company_email)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró empresa con email: {company_email}"
        )
    
    if company.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario {company_email} no es una empresa"
        )
    
    if company.verified:
        return {"message": f"La empresa {company_email} ya está verificada"}
    
    # Verificar empresa
    verified_company = user_service.verify_company(company.id, True)
    
    return {
        "message": f"Empresa {company_email} verificada exitosamente",
        "company": {
            "id": verified_company.id,
            "nombre": verified_company.nombre,
            "email": verified_company.email,
            "verified": verified_company.verified
        }
    }

@router.put("/admin/companies/verify-by-email", response_model=UserResponse)
async def verify_company_by_email(
    company_email: str,
    verification: CompanyVerification,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Verificar empresa por email"""
    user_service = UserService(db)
    
    # Buscar empresa por email
    company = user_service.get_user_by_email(company_email)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró empresa con email: {company_email}"
        )
    
    if company.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario {company_email} no es una empresa"
        )
    
    return user_service.verify_company(company.id, verification.verified)

@router.get("/admin/users", response_model=List[UserResponse])
async def get_all_users_admin(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Ver todos los usuarios (solo admins)"""
    user_service = UserService(db)
    return user_service.get_all_users(skip=skip, limit=limit)

# Función para verificar si es empresa verificada
def require_verified_company(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empresas pueden realizar esta acción"
        )
    if not current_user.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo empresas verificadas pueden agregar recruiters"
        )
    return current_user

# Endpoints para gestión de recruiters
@router.post("/companies/add-recruiter")
async def add_recruiter_to_company(
    recruiter_email: str,
    db: Session = Depends(get_db),
    company: User = Depends(require_verified_company)
):
    """Agregar recruiter a mi empresa"""
    user_service = UserService(db)
    
    try:
        company_recruiter = user_service.add_recruiter_to_company(
            company.id, 
            recruiter_email
        )
        
        return {
            "message": f"Recruiter {recruiter_email} agregado exitosamente",
            "recruiter_id": company_recruiter.recruiter_id,
            "assigned_at": company_recruiter.assigned_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al agregar recruiter: {str(e)}"
        )

@router.get("/companies/my-recruiters")
async def get_my_recruiters(
    db: Session = Depends(get_db),
    company: User = Depends(require_verified_company)
):
    """Ver todos mis recruiters"""
    user_service = UserService(db)
    recruiters = user_service.get_company_recruiters(company.id)
    
    recruiter_list = []
    for rel in recruiters:
        recruiter_user = user_service.get_user_by_id(rel.recruiter_id)
        if recruiter_user:
            recruiter_list.append({
                "id": recruiter_user.id,
                "email": recruiter_user.email,
                "nombre": recruiter_user.nombre,
                "apellido": recruiter_user.apellido,
                "assigned_at": rel.assigned_at,
                "is_active": rel.is_active
            })
    
    return {
        "company": company.nombre,
        "recruiters": recruiter_list,
        "total": len(recruiter_list)
    }

@router.delete("/companies/remove-recruiter")
async def remove_recruiter_from_company(
    recruiter_email: str,
    db: Session = Depends(get_db),
    company: User = Depends(require_verified_company)
):
    """Remover recruiter de mi empresa"""
    user_service = UserService(db)
    
    success = user_service.remove_recruiter_from_company(
        company.id, 
        recruiter_email
    )
    
    if success:
        return {
            "message": f"Recruiter {recruiter_email} removido exitosamente"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo remover el recruiter"
        )

@router.get("/me/recruiting-for")
async def get_recruiting_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ver para qué empresas soy recruiter"""
    if current_user.role != UserRoleEnum.candidato:
        return {
            "message": "Solo candidatos pueden ser recruiters",
            "companies": []
        }
    
    user_service = UserService(db)
    companies = user_service.get_recruiter_companies(current_user.id)
    
    company_list = []
    for rel in companies:
        company_user = user_service.get_user_by_id(rel.company_id)
        if company_user:
            company_list.append({
                "id": company_user.id,
                "nombre": company_user.nombre,
                "email": company_user.email,
                "descripcion": company_user.descripcion,
                "assigned_at": rel.assigned_at,
                "verified": company_user.verified
            })
    
    return {
        "recruiter": f"{current_user.nombre} {current_user.apellido}",
        "companies": company_list,
        "total": len(company_list)
    }

@router.delete("/me/resign-from-company/{company_id}")
async def resign_from_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Renunciar como recruiter de una empresa"""
    if current_user.role != UserRoleEnum.candidato:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo candidatos pueden renunciar como recruiters"
        )

    user_service = UserService(db)

    # Verificar que la empresa existe
    company = user_service.get_user_by_id(company_id)
    if not company or company.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Remover asignaciones de ofertas específicas en JobsAPI
    JOBS_API_URL = os.getenv("JOBS_API_URL", "http://localhost:8002")
    import json

    try:
        async with httpx.AsyncClient() as client:
            # Llamar al endpoint de JobsAPI para limpiar asignaciones
            # Usar request() en lugar de delete() porque httpx 0.25.0 no soporta json/content en delete()
            response = await client.request(
                method="DELETE",
                url=f"{JOBS_API_URL}/api/v1/internal/remove-recruiter-assignments",
                content=json.dumps({
                    "recruiter_id": current_user.id,
                    "company_id": company_id
                }),
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            print(f"JobsAPI cleanup response: {response.status_code} - {response.text}")
            if response.status_code != 200:
                print(f"Warning: JobsAPI returned non-200 status: {response.status_code}")
    except Exception as e:
        print(f"Warning: Could not cleanup job assignments in JobsAPI: {e}")
        import traceback
        print(traceback.format_exc())
        # No fallar la renuncia si JobsAPI no responde

    # Remover la relación de company_recruiters
    success = user_service.remove_recruiter_from_company(
        company_id,
        current_user.email
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo procesar la renuncia"
        )

    # Verificar si le quedan empresas
    remaining_companies = user_service.get_recruiter_companies(current_user.id)

    message = f"Has renunciado como recruiter de {company.nombre}"
    if not remaining_companies:
        message += ". Ya no eres recruiter de ninguna empresa"

    return {
        "message": message,
        "remaining_companies": len(remaining_companies)
    }

@router.get("/admin/candidates", response_model=List[UserResponse])
async def get_all_candidates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Ver todos los candidatos con sus datos y CV analizados (solo admins)"""
    user_service = UserService(db)
    candidates = user_service.get_all_candidates(skip=skip, limit=limit)
    return candidates

@router.post("/admin/cleanup-temp-files")
async def cleanup_temp_files(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Limpiar archivos temporales de registros expirados y huérfanos (solo admins)"""
    user_service = UserService(db)

    # Limpiar registros expirados
    expired_count = user_service.temp_storage.cleanup_expired_registrations()

    # Limpiar archivos huérfanos
    orphaned_count = user_service.temp_storage.cleanup_orphaned_temp_files()

    return {
        "message": "Limpieza de archivos temporales completada",
        "registros_expirados_eliminados": expired_count,
        "archivos_huerfanos_eliminados": orphaned_count,
        "total_eliminado": expired_count + orphaned_count
    }

@router.get("/companies/{company_id}/recruiters")
async def get_company_recruiters_public(
    company_id: int,
    db: Session = Depends(get_db)
):
    """Obtener recruiters activos de una empresa (endpoint público para JobsAPI)"""
    user_service = UserService(db)

    # Verificar que la empresa existe
    company = user_service.get_user_by_id(company_id)
    if not company or company.role != UserRoleEnum.empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Obtener recruiters activos
    recruiters_relations = db.query(CompanyRecruiter).filter(
        CompanyRecruiter.company_id == company_id,
        CompanyRecruiter.is_active == True
    ).all()

    recruiter_list = []
    for rel in recruiters_relations:
        recruiter = user_service.get_user_by_id(rel.recruiter_id)
        if recruiter:
            recruiter_list.append({
                "id": recruiter.id,
                "nombre": recruiter.nombre,
                "apellido": recruiter.apellido,
                "email": recruiter.email,
                "assigned_at": rel.assigned_at
            })

    return recruiter_list