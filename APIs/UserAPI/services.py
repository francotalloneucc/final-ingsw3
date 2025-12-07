from __future__ import annotations  # ⭐ NUEVO: Permite forward references
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile, BackgroundTasks
from typing import List, Optional, TYPE_CHECKING  # ⭐ CORREGIDO: Agregado TYPE_CHECKING
import os
import uuid
import requests
# IMPORTS para email verification
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets  # ⭐ CORREGIDO: Usar secrets en lugar de random
from datetime import datetime, timedelta
# IMPORTS para almacenamiento temporal
import json
from pathlib import Path

# ⭐ CORREGIDO: Imports condicionales para evitar circular imports
if TYPE_CHECKING:
    from models import User, CompanyRecruiter
    from schemas import CandidatoCreate, EmpresaCreate, UserUpdate, CompanyRecruiterCreate

# ⭐ CORREGIDO: Imports normales después
from models import UserRoleEnum
from auth import get_password_hash, verify_password

# 🔒 SEGURIDAD: Rate limiter global (compartido entre requests)
_global_rate_limiter = None

def get_rate_limiter():
    """Obtiene la instancia global del rate limiter (singleton)"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    return _global_rate_limiter

# CLASE - Rate Limiter para verificaciones
class RateLimiter:
    """Maneja límites de intentos de verificación para prevenir brute force"""

    def __init__(self):
        self.attempts = {}  # {email: {"count": int, "blocked_until": datetime}}
        self.max_attempts = 5  # Máximo 5 intentos
        self.block_duration = timedelta(minutes=15)  # Bloqueo de 15 minutos

    def check_and_increment(self, email: str) -> bool:
        """
        Verifica si el email puede intentar verificación.
        Retorna True si puede intentar, False si está bloqueado.
        """
        now = datetime.utcnow()

        # Si el email está en el diccionario
        if email in self.attempts:
            attempt_data = self.attempts[email]

            # Si está bloqueado, verificar si el bloqueo expiró
            if "blocked_until" in attempt_data:
                if now < attempt_data["blocked_until"]:
                    # Aún bloqueado
                    return False
                else:
                    # Bloqueo expiró, resetear
                    del self.attempts[email]

        # Incrementar contador
        if email not in self.attempts:
            self.attempts[email] = {"count": 1, "first_attempt": now}
        else:
            self.attempts[email]["count"] += 1

        # Si superó el límite, bloquear
        if self.attempts[email]["count"] > self.max_attempts:
            self.attempts[email]["blocked_until"] = now + self.block_duration
            return False

        return True

    def reset(self, email: str):
        """Resetea el contador de intentos para un email"""
        if email in self.attempts:
            del self.attempts[email]

    def get_remaining_attempts(self, email: str) -> int:
        """Obtiene intentos restantes para un email"""
        if email not in self.attempts:
            return self.max_attempts
        return max(0, self.max_attempts - self.attempts[email].get("count", 0))

    def get_block_time_remaining(self, email: str) -> Optional[int]:
        """Obtiene minutos restantes de bloqueo, o None si no está bloqueado"""
        if email in self.attempts and "blocked_until" in self.attempts[email]:
            blocked_until = self.attempts[email]["blocked_until"]
            now = datetime.utcnow()
            if now < blocked_until:
                remaining = (blocked_until - now).total_seconds() / 60
                return int(remaining) + 1
        return None

# CLASE - Almacenamiento temporal
class TemporaryStorage:
    """Maneja almacenamiento temporal de registros pendientes de verificación"""

    def __init__(self):
        self.temp_dir = Path("temp_registrations")
        self.temp_dir.mkdir(exist_ok=True)
        print(f"📁 DEBUG: Directorio temporal inicializado: {self.temp_dir.absolute()}")
    
    def save_pending_registration(self, email: str, registration_data: dict, verification_code: str) -> str:
        """Guarda datos de registro temporalmente"""
        temp_data = {
            "registration_data": registration_data,
            "verification_code": verification_code,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        }
        
        # Usar email como nombre de archivo (sanitizado)
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        file_path = self.temp_dir / f"{safe_email}.json"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, indent=2)
            
            print(f"📝 DEBUG: Registro temporal guardado para {email}")
            print(f"📁 DEBUG: Archivo creado en: {file_path.absolute()}")
            print(f"🔑 DEBUG: Código generado: {verification_code}")
            return str(file_path)
        except Exception as e:
            print(f"❌ DEBUG: Error guardando registro temporal: {e}")
            raise
    
    def get_pending_registration(self, email: str) -> dict | None:
        """Obtiene datos de registro temporal"""
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        file_path = self.temp_dir / f"{safe_email}.json"
        
        print(f"🔍 DEBUG: Buscando archivo: {file_path.absolute()}")
        print(f"📁 DEBUG: Archivo existe: {file_path.exists()}")
        
        if not file_path.exists():
            print(f"❌ DEBUG: No se encontró archivo temporal para {email}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                temp_data = json.load(f)
            
            print(f"📖 DEBUG: Archivo leído correctamente")
            print(f"🔑 DEBUG: Código en archivo: {temp_data.get('verification_code')}")
            
            # Verificar si no ha expirado
            expires_at = datetime.fromisoformat(temp_data["expires_at"])
            now = datetime.utcnow()
            print(f"⏰ DEBUG: Expira en: {expires_at}")
            print(f"⏰ DEBUG: Hora actual: {now}")
            print(f"⏰ DEBUG: ¿Expirado?: {now > expires_at}")
            
            if now > expires_at:
                print(f"⚠️ DEBUG: Registro expirado para {email}")
                self.remove_pending_registration(email)  # Limpiar expirado
                return None
            
            print(f"✅ DEBUG: Registro temporal válido para {email}")
            return temp_data
        except Exception as e:
            print(f"❌ DEBUG: Error leyendo registro temporal: {e}")
            return None
    
    def remove_pending_registration(self, email: str) -> bool:
        """Elimina registro temporal"""
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        file_path = self.temp_dir / f"{safe_email}.json"
        
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"🗑️ DEBUG: Registro temporal eliminado para {email}")
                return True
            except Exception as e:
                print(f"❌ DEBUG: Error eliminando archivo: {e}")
                return False
        return False
    
    def cleanup_expired_registrations(self):
        """Limpia registros temporales expirados Y sus archivos asociados"""
        cleaned_count = 0
        for file_path in self.temp_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    temp_data = json.load(f)

                expires_at = datetime.fromisoformat(temp_data["expires_at"])
                if datetime.utcnow() > expires_at:
                    # Limpiar archivos temporales asociados
                    registration_data = temp_data.get("registration_data", {})

                    # Eliminar CV temporal si existe
                    cv_filename = registration_data.get("cv_filename")
                    if cv_filename:
                        cv_path = Path("temp_files") / cv_filename
                        if cv_path.exists():
                            cv_path.unlink()
                            print(f"🗑️ DEBUG: CV temporal eliminado: {cv_filename}")

                    # Eliminar foto temporal si existe
                    pic_filename = registration_data.get("profile_picture_filename")
                    if pic_filename:
                        pic_path = Path("temp_files") / pic_filename
                        if pic_path.exists():
                            pic_path.unlink()
                            print(f"🗑️ DEBUG: Foto temporal eliminada: {pic_filename}")

                    # Eliminar archivo JSON de registro
                    file_path.unlink()
                    cleaned_count += 1
                    print(f"🧹 DEBUG: Registro expirado eliminado: {file_path.name}")
            except Exception as e:
                print(f"❌ DEBUG: Error procesando {file_path}: {e}")

        print(f"✅ DEBUG: Limpieza completada. {cleaned_count} registros expirados eliminados.")
        return cleaned_count

    def cleanup_orphaned_temp_files(self):
        """Limpia archivos temporales sin registro JSON asociado"""
        temp_files_dir = Path("temp_files")
        if not temp_files_dir.exists():
            return 0

        orphaned_count = 0
        # Obtener todos los emails con registros activos
        active_emails = set()
        for json_file in self.temp_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    temp_data = json.load(f)
                    registration_data = temp_data.get("registration_data", {})
                    email = registration_data.get("email", "")
                    safe_email = email.replace("@", "_at_").replace(".", "_dot_")
                    active_emails.add(safe_email)
            except Exception:
                pass

        # Limpiar archivos sin registro JSON correspondiente
        for temp_file in temp_files_dir.glob("temp_*"):
            try:
                # Extraer el email del nombre del archivo
                # Formato: temp_cv_email_at_domain_dot_com_uuid.ext
                parts = temp_file.stem.split("_")
                if len(parts) >= 3:
                    # Buscar si alguno de los emails activos está en el nombre del archivo
                    is_active = any(email in temp_file.name for email in active_emails)

                    if not is_active:
                        # Archivo huérfano - eliminar
                        temp_file.unlink()
                        orphaned_count += 1
                        print(f"🗑️ DEBUG: Archivo huérfano eliminado: {temp_file.name}")
            except Exception as e:
                print(f"❌ DEBUG: Error procesando archivo temporal {temp_file}: {e}")

        print(f"✅ DEBUG: Limpieza de archivos huérfanos completada. {orphaned_count} archivos eliminados.")
        return orphaned_count

class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.temp_storage = TemporaryStorage()
        self.rate_limiter = get_rate_limiter()  # 🔒 SEGURIDAD: Rate limiter global para verificaciones

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Obtiene usuario por email"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Obtiene usuario por ID"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Obtiene todos los usuarios"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User
        return self.db.query(User).offset(skip).limit(limit).all()

    def analyze_cv_with_api(self, cv_file: UploadFile) -> Optional[dict]:
        """
        Analiza el CV usando la CvAnalyzerAPI
        """
        try:
            # 🔒 SEGURIDAD: Obtener API key desde .env
            cv_analyzer_api_key = os.getenv("CV_ANALYZER_API_KEY", "default-secret-key-change-in-production")

            # CORREGIDO: Leer el contenido completo primero
            cv_file.file.seek(0)  # Asegurar que esté al inicio
            file_content = cv_file.file.read()  # Leer todo el contenido
            cv_file.file.seek(0)  # Resetear para uso posterior

            # Preparar el archivo para la API usando el contenido leído
            files = {
                'file': (cv_file.filename, file_content, cv_file.content_type)
            }

            # 🔒 SEGURIDAD: Headers con API key
            headers = {
                'X-API-Key': cv_analyzer_api_key
            }

            # Llamar a CvAnalyzerAPI con autenticación
            response = requests.post(
                'http://localhost:8001/analyze/',
                files=files,
                headers=headers,
                timeout=30  # 30 segundos timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('data', None)
            else:
                print(f"Error en CvAnalyzerAPI: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error conectando con CvAnalyzerAPI: {e}")
            return None
        except Exception as e:
            print(f"Error inesperado analizando CV: {e}")
            return None

    def validate_pdf_fast(self, cv_file: UploadFile) -> bool:
        """
        Validación rápida de PDF sin análisis de Gemini.
        Solo verifica que es un archivo PDF válido.
        """
        try:
            # Verificar content type
            if cv_file.content_type != 'application/pdf':
                print(f"❌ Content type inválido: {cv_file.content_type}")
                return False

            # Leer el inicio del archivo para verificar que es PDF
            cv_file.file.seek(0)
            header = cv_file.file.read(5)
            cv_file.file.seek(0)  # Resetear para uso posterior

            # Los archivos PDF empiezan con "%PDF-"
            if not header.startswith(b'%PDF-'):
                print(f"❌ El archivo no es un PDF válido")
                return False

            print(f"✅ PDF válido: {cv_file.filename}")
            return True

        except Exception as e:
            print(f"❌ Error validando PDF: {e}")
            return False

    # ⭐ CORREGIDO: Generador de códigos usando secrets
    def generate_verification_code(self) -> str:
        """Genera código de 6 dígitos usando secrets (criptográficamente seguro)"""
        code = secrets.randbelow(900000) + 100000  # Asegura 6 dígitos (100000-999999)
        print(f"🔑 DEBUG: Código generado: {code}")
        return str(code)

    def send_verification_email(self, email: str, code: str):
        """Envía email con código de verificación"""
        try:
            # Obtener configuración de email del .env
            sender_email = os.getenv("EMAIL_USER")
            sender_password = os.getenv("EMAIL_PASSWORD")
            
            print(f"📧 DEBUG: Intentando enviar email a {email}")
            print(f"📧 DEBUG: Sender configurado: {sender_email is not None}")
            
            if not sender_email or not sender_password:
                print("❌ DEBUG: EMAIL_USER y EMAIL_PASSWORD no configurados en .env")
                return
            
            # Configurar mensaje
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = email
            message["Subject"] = "Verificación de Email - Polo52"
            
            # Cuerpo del email
            body = f"""
¡Hola!

Tu código de verificación para Polo52 es: {code}

Este código expira en 15 minutos.

¡Bienvenido a Polo52!

---
Equipo Polo52
            """
            
            message.attach(MIMEText(body, "plain"))
            
            # Enviar email usando Gmail
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, sender_password)
            text = message.as_string()
            server.sendmail(sender_email, email, text)
            server.quit()
            
            print(f"✅ DEBUG: Email de verificación enviado a {email}")
            
        except Exception as e:
            print(f"❌ DEBUG: Error enviando email: {e}")
            # No lanzar excepción para que el registro no falle por problemas de email

    def verify_email_code(self, email: str, code: str) -> bool:
        """Verifica el código de email usando almacenamiento temporal con rate limiting"""
        print(f"🔍 DEBUG: === INICIANDO VERIFICACIÓN ===")
        print(f"🔍 DEBUG: Email: {email}")
        print(f"🔍 DEBUG: Código recibido: {code}")

        # 🔒 SEGURIDAD: Verificar rate limiting
        if not self.rate_limiter.check_and_increment(email):
            block_time = self.rate_limiter.get_block_time_remaining(email)
            print(f"🚫 DEBUG: Email {email} bloqueado por rate limiting")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos fallidos. Intenta nuevamente en {block_time} minutos."
            )

        # Obtener registro temporal
        temp_data = self.temp_storage.get_pending_registration(email)
        if not temp_data:
            print(f"❌ DEBUG: No se encontró registro temporal para {email}")
            return False

        stored_code = temp_data["verification_code"]
        print(f"🔑 DEBUG: Código almacenado: {stored_code}")
        print(f"🔑 DEBUG: ¿Códigos coinciden?: {stored_code == code}")

        # Verificar código
        if stored_code != code:
            remaining = self.rate_limiter.get_remaining_attempts(email)
            print(f"❌ DEBUG: Código inválido para {email}. Intentos restantes: {remaining}")
            return False

        # 🔒 SEGURIDAD: Código correcto - resetear contador
        self.rate_limiter.reset(email)
        print(f"✅ DEBUG: Código verificado correctamente para {email}")
        return True

    def resend_verification_code(self, email: str) -> dict:
        """
        Reenvía código de verificación con cooldown de 2 minutos.
        Retorna dict con success y mensaje/tiempo_restante.
        """
        print(f"🔄 DEBUG: Reenviando código para {email}")

        # Verificar que hay un registro temporal
        temp_data = self.temp_storage.get_pending_registration(email)
        if not temp_data:
            print(f"❌ DEBUG: No hay registro temporal para reenviar a {email}")
            return {"success": False, "message": "No hay registro pendiente para este email"}

        # 🔒 COOLDOWN: Verificar si se puede reenviar (2 minutos entre reenvíos)
        COOLDOWN_MINUTES = 2
        now = datetime.utcnow()

        last_resend_str = temp_data.get("last_resend_at")
        if last_resend_str:
            last_resend = datetime.fromisoformat(last_resend_str)
            time_elapsed = (now - last_resend).total_seconds() / 60  # en minutos

            if time_elapsed < COOLDOWN_MINUTES:
                time_remaining = int(COOLDOWN_MINUTES - time_elapsed) + 1
                print(f"⏱️ DEBUG: Cooldown activo. Tiempo restante: {time_remaining} minutos")
                return {
                    "success": False,
                    "message": f"Debes esperar {time_remaining} minuto(s) antes de reenviar el código",
                    "seconds_remaining": int((COOLDOWN_MINUTES - time_elapsed) * 60)
                }

        # Generar nuevo código
        verification_code = self.generate_verification_code()

        # Actualizar el registro temporal con nuevo código, tiempo y timestamp del reenvío
        registration_data = temp_data["registration_data"]

        # Guardar con el nuevo timestamp de reenvío
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        file_path = self.temp_storage.temp_dir / f"{safe_email}.json"

        updated_temp_data = {
            "registration_data": registration_data,
            "verification_code": verification_code,
            "created_at": temp_data.get("created_at", now.isoformat()),
            "expires_at": temp_data.get("expires_at", (now + timedelta(minutes=15)).isoformat()),
            "last_resend_at": now.isoformat()  # 🆕 Timestamp del último reenvío
        }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(updated_temp_data, f, indent=2)
            print(f"📝 DEBUG: Registro actualizado con nuevo código y timestamp")
        except Exception as e:
            print(f"❌ DEBUG: Error actualizando registro: {e}")
            return {"success": False, "message": "Error al actualizar el registro"}

        # Enviar email
        try:
            self.send_verification_email(email, verification_code)
            print(f"✅ DEBUG: Código reenviado exitosamente a {email}")
            return {
                "success": True,
                "message": "Código reenviado exitosamente",
                "cooldown_seconds": COOLDOWN_MINUTES * 60
            }
        except Exception as e:
            print(f"❌ DEBUG: Error enviando email: {e}")
            return {"success": False, "message": "Error al enviar el email"}

    # NUEVO MÉTODO - Registro temporal de candidato
    def create_pending_candidato(self, candidato, cv_file: UploadFile, profile_picture: Optional[UploadFile] = None) -> dict:
        """Crea registro temporal de candidato (NO lo guarda en DB hasta verificar email)"""
        # ⭐ CORREGIDO: Import local de schemas para evitar problemas
        from schemas import CandidatoCreate
        
        print(f"🚀 DEBUG: === INICIANDO REGISTRO CANDIDATO ===")
        print(f"📧 DEBUG: Email: {candidato.email}")
        
        # 1. Verificar si el usuario ya existe en DB
        existing_user = self.get_user_by_email(email=candidato.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        # 2. Verificar si ya hay un registro temporal pendiente
        existing_temp = self.temp_storage.get_pending_registration(candidato.email)
        if existing_temp:
            print(f"⚠️ DEBUG: Ya existe registro temporal para {candidato.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya hay un registro pendiente para este email. Verifica tu email o espera a que expire."
            )
        
        # 3. Analizar CV con CvAnalyzerAPI
        print(f"🤖 DEBUG: Analizando CV...")
        cv_analysis_result = self.analyze_cv_with_api(cv_file)
        if cv_analysis_result is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es un CV válido o no se pudo analizar"
            )
        print(f"✅ DEBUG: CV analizado correctamente")
        
        # 4. Guardar archivos temporalmente
        cv_filename = self.save_temp_cv_file(cv_file, candidato.email)
        
        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_temp_profile_picture(profile_picture, candidato.email)
        
        # 5. Preparar datos para almacenamiento temporal
        registration_data = {
            "user_type": "candidato",
            "email": candidato.email,
            "password": candidato.password,  # Se hasheará al crear el usuario real
            "nombre": candidato.nombre,
            "apellido": candidato.apellido,
            "genero": candidato.genero.value,
            "fecha_nacimiento": candidato.fecha_nacimiento.isoformat(),
            "cv_filename": cv_filename,
            "cv_analysis_result": cv_analysis_result,
            "profile_picture_filename": profile_picture_filename
        }
        
        # 6. Generar código de verificación
        verification_code = self.generate_verification_code()
        
        # 7. Guardar temporalmente
        print(f"💾 DEBUG: Guardando registro temporal...")
        file_path = self.temp_storage.save_pending_registration(
            candidato.email, 
            registration_data, 
            verification_code
        )
        print(f"📁 DEBUG: Archivo guardado en: {file_path}")
        
        # 8. Enviar email de verificación
        print(f"📧 DEBUG: Enviando email de verificación...")
        self.send_verification_email(candidato.email, verification_code)
        
        print(f"✅ DEBUG: Proceso de registro temporal completado para {candidato.email}")
        
        return {
            "message": "Registro iniciado. Verifica tu email para completar el proceso.",
            "email": candidato.email,
            "expires_in_minutes": 15
        }

    # ⚡ NUEVO MÉTODO OPTIMIZADO - Registro rápido con procesamiento en background
    def create_pending_candidato_fast(self, candidato, cv_file: UploadFile, profile_picture: Optional[UploadFile], background_tasks: BackgroundTasks) -> dict:
        """
        Versión optimizada de create_pending_candidato que responde inmediatamente.
        El análisis del CV y envío de email se hacen en background.
        """
        from schemas import CandidatoCreate

        print(f"🚀 DEBUG: === INICIANDO REGISTRO RÁPIDO CANDIDATO ===")
        print(f"📧 DEBUG: Email: {candidato.email}")

        # 1. Verificar si el usuario ya existe en DB
        existing_user = self.get_user_by_email(email=candidato.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )

        # 2. Verificar si ya hay un registro temporal pendiente
        existing_temp = self.temp_storage.get_pending_registration(candidato.email)
        if existing_temp:
            print(f"⚠️ DEBUG: Ya existe registro temporal para {candidato.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya hay un registro pendiente para este email. Verifica tu email o espera a que expire."
            )

        # 3. Validación RÁPIDA del PDF (sin Gemini)
        print(f"📄 DEBUG: Validando PDF...")
        if not self.validate_pdf_fast(cv_file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser un PDF válido"
            )
        print(f"✅ DEBUG: PDF válido")

        # 4. Guardar archivos temporalmente
        cv_filename = self.save_temp_cv_file(cv_file, candidato.email)

        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_temp_profile_picture(profile_picture, candidato.email)

        # 5. Generar código de verificación
        verification_code = self.generate_verification_code()

        # 6. Preparar datos temporales (SIN cv_analysis_result aún)
        registration_data = {
            "user_type": "candidato",
            "email": candidato.email,
            "password": candidato.password,
            "nombre": candidato.nombre,
            "apellido": candidato.apellido,
            "genero": candidato.genero.value,
            "fecha_nacimiento": candidato.fecha_nacimiento.isoformat(),
            "cv_filename": cv_filename,
            "cv_analysis_result": None,  # Se analizará en background
            "profile_picture_filename": profile_picture_filename
        }

        # 7. Guardar temporalmente
        print(f"💾 DEBUG: Guardando registro temporal...")
        file_path = self.temp_storage.save_pending_registration(
            candidato.email,
            registration_data,
            verification_code
        )
        print(f"📁 DEBUG: Archivo guardado en: {file_path}")

        # 8. ⚡ Programar análisis de CV + envío de email en BACKGROUND
        print(f"📋 DEBUG: Programando análisis y envío de email en background...")
        background_tasks.add_task(
            self._process_cv_and_send_email_background,
            candidato.email,
            cv_filename,
            verification_code
        )

        print(f"✅ DEBUG: Respuesta inmediata enviada para {candidato.email}")

        # 9. ⚡ RESPUESTA INMEDIATA (sin esperar análisis ni email)
        return {
            "message": "Registro iniciado. Te enviaremos un email de verificación en unos momentos.",
            "email": candidato.email,
            "expires_in_minutes": 15
        }

    def _process_cv_and_send_email_background(self, email: str, cv_filename: str, verification_code: str):
        """
        Función auxiliar que se ejecuta en background para:
        1. Analizar el CV con Gemini
        2. Actualizar los datos temporales con el análisis
        3. Enviar el email de verificación
        """
        try:
            print(f"🔄 BACKGROUND: Iniciando procesamiento para {email}")

            # 1. Abrir el CV guardado temporalmente
            temp_cv_path = os.path.join("temp_files", cv_filename)

            if not os.path.exists(temp_cv_path):
                print(f"❌ BACKGROUND ERROR: CV no encontrado en {temp_cv_path}")
                return

            # 2. Crear un UploadFile simulado para analyze_cv_with_api
            with open(temp_cv_path, 'rb') as f:
                from fastapi import UploadFile
                from io import BytesIO

                cv_content = f.read()
                fake_file = BytesIO(cv_content)
                fake_upload = UploadFile(filename=cv_filename, file=fake_file)

                # 3. Analizar CV con Gemini
                print(f"🤖 BACKGROUND: Analizando CV con Gemini...")
                cv_analysis_result = self.analyze_cv_with_api(fake_upload)

                if cv_analysis_result:
                    print(f"✅ BACKGROUND: CV analizado correctamente")

                    # 4. Actualizar registro temporal con el análisis
                    temp_data = self.temp_storage.get_pending_registration(email)
                    if temp_data:
                        temp_data["registration_data"]["cv_analysis_result"] = cv_analysis_result

                        # Guardar actualización
                        temp_file_path = os.path.join(self.temp_storage.temp_registrations_dir, f"{email.replace('@', '_at_').replace('.', '_dot_')}.json")
                        with open(temp_file_path, 'w') as f:
                            json.dump(temp_data, f, indent=2)

                        print(f"💾 BACKGROUND: Datos actualizados con análisis")
                else:
                    print(f"⚠️ BACKGROUND: No se pudo analizar el CV")

            # 5. Enviar email de verificación
            print(f"📧 BACKGROUND: Enviando email...")
            self.send_verification_email(email, verification_code)
            print(f"✅ BACKGROUND: Email enviado a {email}")

        except Exception as e:
            print(f"❌ BACKGROUND ERROR procesando {email}: {e}")

    # NUEVO MÉTODO - Completar registro después de verificación
    def complete_candidato_registration(self, email: str, verification_code: str) -> User:
        """Completa el registro del candidato después de verificar email"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User, GenderEnum
        from datetime import date
        
        print(f"🏁 DEBUG: === COMPLETANDO REGISTRO CANDIDATO ===")
        print(f"📧 DEBUG: Email: {email}")
        print(f"🔑 DEBUG: Código: {verification_code}")
        
        # 1. Verificar código
        if not self.verify_email_code(email, verification_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código de verificación inválido o expirado"
            )
        
        # 2. Obtener datos temporales
        temp_data = self.temp_storage.get_pending_registration(email)
        if not temp_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se encontraron datos de registro pendientes"
            )
        
        registration_data = temp_data["registration_data"]
        
        # Verificar que sea un candidato
        if registration_data.get("user_type") != "candidato":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los datos de registro no corresponden a un candidato"
            )
        
        print(f"📋 DEBUG: Datos temporales recuperados")
        
        # 3. Mover archivos temporales a ubicaciones permanentes
        permanent_cv, permanent_pic = self.move_temp_files_to_permanent(
            registration_data.get("cv_filename"),
            registration_data.get("profile_picture_filename")
        )
        print(f"📁 DEBUG: Archivos movidos a permanentes")
        
        # 4. Crear usuario en la base de datos
        hashed_password = get_password_hash(registration_data["password"])
        db_user = User(
            email=registration_data["email"],
            hashed_password=hashed_password,
            role=UserRoleEnum.candidato,
            nombre=registration_data["nombre"],
            apellido=registration_data["apellido"],
            genero=GenderEnum(registration_data["genero"]),
            fecha_nacimiento=date.fromisoformat(registration_data["fecha_nacimiento"]),
            cv_filename=permanent_cv,
            cv_analizado=registration_data["cv_analysis_result"],
            profile_picture=permanent_pic,
            descripcion=None,
            verified=False,
            email_verified=True,  # Ya verificado!
            verification_code=None,
            verification_expires=None
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        print(f"✅ DEBUG: Usuario creado en base de datos con ID: {db_user.id}")
        
        # 5. Limpiar registro temporal
        self.temp_storage.remove_pending_registration(email)
        print(f"🧹 DEBUG: Registro temporal limpiado")
        
        print(f"🎉 DEBUG: Registro completado exitosamente para {email}")
        return db_user

    # ⭐ NUEVO MÉTODO - Registro temporal de empresa
    def create_empresa(self, empresa, profile_picture: Optional[UploadFile] = None) -> dict:
        """Crea registro temporal de empresa (NO lo guarda en DB hasta verificar email)"""
        # ⭐ CORREGIDO: Import local de schemas para evitar problemas
        from schemas import EmpresaCreate
        
        print(f"🏢 DEBUG: === INICIANDO REGISTRO EMPRESA ===")
        print(f"📧 DEBUG: Email: {empresa.email}")
        
        # 1. Verificar si el usuario ya existe en DB
        existing_user = self.get_user_by_email(email=empresa.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        # 2. Verificar si ya hay un registro temporal pendiente
        existing_temp = self.temp_storage.get_pending_registration(empresa.email)
        if existing_temp:
            print(f"⚠️ DEBUG: Ya existe registro temporal para {empresa.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya hay un registro pendiente para este email. Verifica tu email o espera a que expire."
            )
        
        # 3. Guardar foto de perfil temporalmente
        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_temp_profile_picture(profile_picture, empresa.email)
        
        # 4. Preparar datos para almacenamiento temporal
        registration_data = {
            "user_type": "empresa",
            "email": empresa.email,
            "password": empresa.password,  # Se hasheará al crear el usuario real
            "nombre": empresa.nombre,
            "descripcion": empresa.descripcion,
            "profile_picture_filename": profile_picture_filename
        }
        
        # 5. Generar código de verificación
        verification_code = self.generate_verification_code()
        
        # 6. Guardar temporalmente
        print(f"💾 DEBUG: Guardando registro temporal de empresa...")
        file_path = self.temp_storage.save_pending_registration(
            empresa.email, 
            registration_data, 
            verification_code
        )
        print(f"📁 DEBUG: Archivo guardado en: {file_path}")
        
        # 7. Enviar email de verificación
        print(f"📧 DEBUG: Enviando email de verificación...")
        self.send_verification_email(empresa.email, verification_code)
        
        print(f"✅ DEBUG: Proceso de registro temporal de empresa completado para {empresa.email}")
        
        return {
            "message": "Registro de empresa iniciado. Verifica tu email para completar el proceso.",
            "email": empresa.email,
            "expires_in_minutes": 15
        }

    # ⭐ NUEVO MÉTODO - Completar registro de empresa
    def complete_empresa_registration(self, email: str, verification_code: str) -> User:
        """Completa el registro de empresa después de verificar email"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User
        
        print(f"🏁 DEBUG: === COMPLETANDO REGISTRO EMPRESA ===")
        print(f"📧 DEBUG: Email: {email}")
        print(f"🔑 DEBUG: Código: {verification_code}")
        
        # 1. Verificar código
        if not self.verify_email_code(email, verification_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código de verificación inválido o expirado"
            )
        
        # 2. Obtener datos temporales
        temp_data = self.temp_storage.get_pending_registration(email)
        if not temp_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se encontraron datos de registro pendientes"
            )
        
        registration_data = temp_data["registration_data"]
        
        # Verificar que sea una empresa
        if registration_data.get("user_type") != "empresa":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los datos de registro no corresponden a una empresa"
            )
        
        print(f"📋 DEBUG: Datos temporales de empresa recuperados")
        
        # 3. Mover archivo temporal a ubicación permanente
        permanent_pic = None
        if registration_data.get("profile_picture_filename"):
            _, permanent_pic = self.move_temp_files_to_permanent(
                None,  # No CV para empresas
                registration_data.get("profile_picture_filename")
            )
            print(f"📁 DEBUG: Foto de empresa movida a permanente")
        
        # 4. Crear empresa en la base de datos
        hashed_password = get_password_hash(registration_data["password"])
        db_user = User(
            email=registration_data["email"],
            hashed_password=hashed_password,
            role=UserRoleEnum.empresa,
            nombre=registration_data["nombre"],
            descripcion=registration_data["descripcion"],
            profile_picture=permanent_pic,
            verified=False,  # Las empresas requieren verificación admin
            # Campos NULL para empresas
            apellido=None,
            genero=None,
            fecha_nacimiento=None,
            cv_filename=None,
            cv_analizado=None,
            # Email ya verificado
            email_verified=True,
            verification_code=None,
            verification_expires=None
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        print(f"✅ DEBUG: Empresa creada en base de datos con ID: {db_user.id}")
        
        # 5. Limpiar registro temporal
        self.temp_storage.remove_pending_registration(email)
        print(f"🧹 DEBUG: Registro temporal de empresa limpiado")
        
        print(f"🎉 DEBUG: Registro de empresa completado exitosamente para {email}")
        return db_user

    # MÉTODOS para archivos temporales
    def save_temp_cv_file(self, cv_file: UploadFile, email: str) -> str:
        """Guarda CV temporalmente"""
        # 🔒 SEGURIDAD: Validar tamaño de archivo (máximo 10MB para CVs)
        MAX_CV_SIZE = 10 * 1024 * 1024  # 10MB en bytes

        os.makedirs("temp_files", exist_ok=True)

        cv_file.file.seek(0)  # Reset file pointer
        content = cv_file.file.read()

        # Validar tamaño
        if len(content) > MAX_CV_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El CV excede el tamaño máximo permitido de 10MB. Tamaño: {len(content) / (1024*1024):.2f}MB"
            )

        file_extension = cv_file.filename.split(".")[-1]
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        temp_filename = f"temp_cv_{safe_email}_{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("temp_files", temp_filename)

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        print(f"📄 DEBUG: CV temporal guardado: {temp_filename} ({len(content) / 1024:.2f}KB)")
        return temp_filename

    def save_temp_profile_picture(self, picture_file: UploadFile, email: str) -> str:
        """Guarda foto de perfil temporalmente"""
        # 🔒 SEGURIDAD: Validar tamaño de archivo (máximo 5MB para fotos)
        MAX_PICTURE_SIZE = 5 * 1024 * 1024  # 5MB en bytes

        os.makedirs("temp_files", exist_ok=True)

        # Leer contenido y validar tamaño
        picture_file.file.seek(0)  # Reset file pointer
        content = picture_file.file.read()

        if len(content) > MAX_PICTURE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"La foto excede el tamaño máximo permitido de 5MB. Tamaño: {len(content) / (1024*1024):.2f}MB"
            )

        # Validar extensión
        allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
        file_extension = picture_file.filename.split(".")[-1].lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de archivo no válido. Permitidos: {', '.join(allowed_extensions)}"
            )

        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        temp_filename = f"temp_pic_{safe_email}_{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("temp_files", temp_filename)

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        print(f"📷 DEBUG: Foto temporal guardada: {temp_filename} ({len(content) / 1024:.2f}KB)")
        return temp_filename

    def move_temp_files_to_permanent(self, temp_cv: str = None, temp_pic: str = None) -> tuple:
        """Mueve archivos temporales a ubicaciones permanentes"""
        permanent_cv = None
        permanent_pic = None
        
        if temp_cv:
            # Mover CV
            temp_path = os.path.join("temp_files", temp_cv)
            if os.path.exists(temp_path):
                file_extension = temp_cv.split(".")[-1]
                permanent_cv = f"{uuid.uuid4()}.{file_extension}"
                permanent_path = os.path.join("uploaded_cvs", permanent_cv)
                os.makedirs("uploaded_cvs", exist_ok=True)
                os.rename(temp_path, permanent_path)
                print(f"📄 DEBUG: CV movido: {temp_cv} → {permanent_cv}")
        
        if temp_pic:
            # Mover foto
            temp_path = os.path.join("temp_files", temp_pic)
            if os.path.exists(temp_path):
                file_extension = temp_pic.split(".")[-1]
                permanent_pic = f"{uuid.uuid4()}.{file_extension}"
                permanent_path = os.path.join("profile_pictures", permanent_pic)
                os.makedirs("profile_pictures", exist_ok=True)
                os.rename(temp_path, permanent_path)
                print(f"📷 DEBUG: Foto movida: {temp_pic} → {permanent_pic}")
        
        return permanent_cv, permanent_pic

    # MANTENER método original para compatibilidad (DESHABILITADO)
    def create_candidato(self, candidato, cv_file: UploadFile, profile_picture: Optional[UploadFile] = None) -> User:
        """DEPRECATED: Usar create_pending_candidato + complete_candidato_registration"""
        # Este método se mantiene solo para compatibilidad
        # En el nuevo flujo no se debe usar
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este endpoint está deprecado. Usar el nuevo flujo de verificación de email."
        )

    def create_admin(self, admin_email: str, admin_password: str, admin_name: str, profile_picture: Optional[UploadFile] = None) -> User:
        """Crear admin - solo para uso interno/scripts"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User
        
        db_user = self.get_user_by_email(email=admin_email)
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        # Guardar la foto de perfil si se proporciona
        profile_picture_filename = None
        if profile_picture:
            profile_picture_filename = self.save_profile_picture(profile_picture)
        
        hashed_password = get_password_hash(admin_password)
        db_user = User(
            email=admin_email,
            hashed_password=hashed_password,
            role=UserRoleEnum.admin,
            nombre=admin_name,
            profile_picture=profile_picture_filename,
            verified=True,  # Admins siempre verificados
            # Campos NULL para admin
            apellido=None,
            genero=None,
            fecha_nacimiento=None,
            cv_filename=None,
            cv_analizado=None,
            descripcion=None,
            # Admins no necesitan verificación de email
            email_verified=True,
            verification_code=None,
            verification_expires=None
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def update_user(self, user_id: int, user_update, cv_file: Optional[UploadFile] = None, profile_picture: Optional[UploadFile] = None) -> User:
        """Actualizar usuario"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User
        from schemas import UserUpdate
        
        db_user = self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        update_data = user_update.dict(exclude_unset=True)
        
        # Si se proporciona un nuevo CV, guardarlo y analizarlo (solo para candidatos)
        if cv_file and db_user.role == UserRoleEnum.candidato:
            # NUEVO: Analizar nuevo CV
            cv_analysis_result = self.analyze_cv_with_api(cv_file)
            if cv_analysis_result is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo no es un CV válido o no se pudo analizar"
                )
            
            # Eliminar el CV anterior si existe
            if db_user.cv_filename:
                old_cv_path = os.path.join("uploaded_cvs", db_user.cv_filename)
                if os.path.exists(old_cv_path):
                    os.remove(old_cv_path)
            
            # Guardar el nuevo CV y análisis
            update_data["cv_filename"] = self.save_cv_file(cv_file)
            update_data["cv_analizado"] = cv_analysis_result  # NUEVO
        
        # Si se proporciona una nueva foto de perfil, guardarla (para todos los roles)
        if profile_picture:
            # Eliminar la foto anterior si existe
            if db_user.profile_picture:
                old_picture_path = os.path.join("profile_pictures", db_user.profile_picture)
                if os.path.exists(old_picture_path):
                    os.remove(old_picture_path)
            
            # Guardar la nueva foto
            update_data["profile_picture"] = self.save_profile_picture(profile_picture)
        
        # Actualizar solo los campos permitidos según el rol del usuario
        for field, value in update_data.items():
            if hasattr(db_user, field):
                # Validar que el campo sea apropiado para el rol de usuario
                if db_user.role == UserRoleEnum.candidato:
                    # Candidatos no pueden actualizar descripcion
                    if field != "descripcion":
                        setattr(db_user, field, value)
                elif db_user.role == UserRoleEnum.empresa:
                    # Empresas no pueden actualizar campos específicos de candidatos
                    if field in ["nombre", "descripcion", "profile_picture"]:
                        setattr(db_user, field, value)
                elif db_user.role == UserRoleEnum.admin:
                    # Admins pueden actualizar nombre y foto
                    if field in ["nombre", "profile_picture"]:
                        setattr(db_user, field, value)
        
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def verify_company(self, company_id: int, verified: bool) -> User:
        """Solo para uso de admins"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User
        
        company = self.get_user_by_id(company_id)
        if not company or company.role != UserRoleEnum.empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada"
            )
        
        company.verified = verified
        self.db.commit()
        self.db.refresh(company)
        return company

    def delete_user(self, user_id: int) -> bool:
        """Eliminar usuario"""
        db_user = self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Eliminar el archivo CV si existe
        if db_user.cv_filename:
            cv_path = os.path.join("uploaded_cvs", db_user.cv_filename)
            if os.path.exists(cv_path):
                os.remove(cv_path)
        
        # Eliminar la foto de perfil si existe
        if db_user.profile_picture:
            picture_path = os.path.join("profile_pictures", db_user.profile_picture)
            if os.path.exists(picture_path):
                os.remove(picture_path)
        
        self.db.delete(db_user)
        self.db.commit()
        return True

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Autenticar usuario"""
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def save_cv_file(self, cv_file: UploadFile) -> str:
        """Guardar archivo CV permanente"""
        # Crear directorio si no existe
        os.makedirs("uploaded_cvs", exist_ok=True)
        
        # Generar nombre único para el archivo
        file_extension = cv_file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("uploaded_cvs", unique_filename)
        
        # Guardar el archivo
        with open(file_path, "wb") as buffer:
            content = cv_file.file.read()
            buffer.write(content)
        
        return unique_filename

    def save_profile_picture(self, picture_file: UploadFile) -> str:
        """Guardar foto de perfil permanente"""
        # Crear directorio si no existe
        os.makedirs("profile_pictures", exist_ok=True)
        
        # Validar que sea una imagen
        allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
        file_extension = picture_file.filename.split(".")[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de archivo no válido. Permitidos: {', '.join(allowed_extensions)}"
            )
        
        # Generar nombre único para el archivo
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("profile_pictures", unique_filename)
        
        # Guardar el archivo
        with open(file_path, "wb") as buffer:
            content = picture_file.file.read()
            buffer.write(content)
        
        return unique_filename

    def get_unverified_companies(self) -> List[User]:
        """Obtener empresas no verificadas"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User
        
        return self.db.query(User).filter(
            User.role == UserRoleEnum.empresa,
            User.verified == False
        ).all()

    # Métodos para gestión de recruiters
    def add_recruiter_to_company(self, company_id: int, recruiter_email: str):
        """Agregar recruiter a una empresa (solo empresas verificadas)"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import CompanyRecruiter
        
        # Verificar que la empresa existe y está verificada
        company = self.get_user_by_id(company_id)
        if not company or company.role != UserRoleEnum.empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada"
            )
        
        if not company.verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo empresas verificadas pueden agregar recruiters"
            )
        
        # Buscar el candidato por email
        recruiter = self.get_user_by_email(recruiter_email)
        if not recruiter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró candidato con email: {recruiter_email}"
            )
        
        if recruiter.role != UserRoleEnum.candidato:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo candidatos pueden ser recruiters"
            )
        
        # Verificar que no sea ya recruiter de esta empresa
        existing = self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.company_id == company_id,
            CompanyRecruiter.recruiter_id == recruiter.id,
            CompanyRecruiter.is_active == True
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{recruiter_email} ya es recruiter de esta empresa"
            )
        
        # Crear relación company-recruiter
        company_recruiter = CompanyRecruiter(
            company_id=company_id,
            recruiter_id=recruiter.id,
            is_active=True
        )
        
        self.db.add(company_recruiter)
        self.db.commit()
        self.db.refresh(company_recruiter)
        
        return company_recruiter

    def get_company_recruiters(self, company_id: int):
        """Obtener todos los recruiters activos de una empresa"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import CompanyRecruiter
        
        return self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.company_id == company_id,
            CompanyRecruiter.is_active == True
        ).all()

    def get_recruiter_companies(self, recruiter_id: int):
        """Obtener todas las empresas para las que trabaja un recruiter"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import CompanyRecruiter
        
        return self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.recruiter_id == recruiter_id,
            CompanyRecruiter.is_active == True
        ).all()

    def remove_recruiter_from_company(self, company_id: int, recruiter_email: str) -> bool:
        """Remover recruiter de una empresa"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import CompanyRecruiter
        
        # Buscar recruiter
        recruiter = self.get_user_by_email(recruiter_email)
        if not recruiter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró recruiter con email: {recruiter_email}"
            )
        
        # Buscar relación activa
        company_recruiter = self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.company_id == company_id,
            CompanyRecruiter.recruiter_id == recruiter.id,
            CompanyRecruiter.is_active == True
        ).first()
        
        if not company_recruiter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{recruiter_email} no es recruiter de esta empresa"
            )
        
        # Desactivar relación (no eliminar para mantener historial)
        company_recruiter.is_active = False
        self.db.commit()
        
        return True

    def is_recruiter_for_company(self, recruiter_id: int, company_id: int) -> bool:
        """Verificar si un usuario es recruiter activo de una empresa específica"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import CompanyRecruiter
        
        relation = self.db.query(CompanyRecruiter).filter(
            CompanyRecruiter.company_id == company_id,
            CompanyRecruiter.recruiter_id == recruiter_id,
            CompanyRecruiter.is_active == True
        ).first()
        
        return relation is not None

    def get_all_candidates(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Obtener todos los usuarios candidatos con sus datos completos"""
        # ⭐ CORREGIDO: Import local para evitar problemas de tipo
        from models import User

        return self.db.query(User).filter(
            User.role == UserRoleEnum.candidato
        ).offset(skip).limit(limit).all()

    # ⭐ MÉTODOS SIMPLIFICADOS - Registro directo sin verificación (para propósitos académicos)

    def create_candidato_simple(self, candidato_data, profile_picture: Optional[UploadFile] = None):
        """Crea candidato directamente sin CV ni verificación de email"""
        from models import User
        from schemas import CandidatoCreate

        # Verificar si el email ya existe
        existing_user = self.get_user_by_email(email=candidato_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )

        # Guardar foto de perfil si existe
        profile_pic_filename = None
        if profile_picture:
            profile_pic_filename = self.save_profile_picture(profile_picture, candidato_data.email)

        # Crear usuario directamente en la base de datos
        hashed_password = get_password_hash(candidato_data.password)
        db_user = User(
            email=candidato_data.email,
            hashed_password=hashed_password,
            role=UserRoleEnum.candidato,
            nombre=candidato_data.nombre,
            apellido=candidato_data.apellido,
            genero=candidato_data.genero,
            fecha_nacimiento=candidato_data.fecha_nacimiento,
            profile_picture=profile_pic_filename,
            verified=True,  # Directamente verificado
            email_verified=True,  # Email ya verificado
            # Sin CV
            cv_filename=None,
            cv_analizado=None,
            # Campos NULL para candidatos
            descripcion=None,
            verification_code=None,
            verification_expires=None
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        return db_user

    def create_empresa_simple(self, empresa_data, profile_picture: Optional[UploadFile] = None):
        """Crea empresa directamente sin verificación de email"""
        from models import User
        from schemas import EmpresaCreate

        # Verificar si el email ya existe
        existing_user = self.get_user_by_email(email=empresa_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )

        # Guardar foto de perfil si existe
        profile_pic_filename = None
        if profile_picture:
            profile_pic_filename = self.save_profile_picture(profile_picture, empresa_data.email)

        # Crear usuario directamente en la base de datos
        hashed_password = get_password_hash(empresa_data.password)
        db_user = User(
            email=empresa_data.email,
            hashed_password=hashed_password,
            role=UserRoleEnum.empresa,
            nombre=empresa_data.nombre,
            descripcion=empresa_data.descripcion,
            profile_picture=profile_pic_filename,
            verified=True,  # Directamente verificado (sin aprobación de admin)
            email_verified=True,  # Email ya verificado
            # Campos NULL para empresas
            apellido=None,
            genero=None,
            fecha_nacimiento=None,
            cv_filename=None,
            cv_analizado=None,
            verification_code=None,
            verification_expires=None
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        return db_user

    def save_profile_picture(self, picture_file: UploadFile, email: str) -> str:
        """Guarda foto de perfil permanentemente"""
        # Crear directorio si no existe
        os.makedirs("profile_pictures", exist_ok=True)

        # Validar tamaño (máximo 5MB)
        MAX_PIC_SIZE = 5 * 1024 * 1024
        picture_file.file.seek(0)
        content = picture_file.file.read()

        if len(content) > MAX_PIC_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"La foto excede el tamaño máximo de 5MB"
            )

        # Generar nombre de archivo único
        file_extension = picture_file.filename.split(".")[-1]
        safe_email = email.replace("@", "_at_").replace(".", "_dot_")
        filename = f"profile_{safe_email}_{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("profile_pictures", filename)

        # Guardar archivo
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        return filename