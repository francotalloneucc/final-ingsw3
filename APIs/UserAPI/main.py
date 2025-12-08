from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routes import router
import os

# Solo crear las tablas si no existen (NO borrar las existentes)
Base.metadata.create_all(bind=engine)

# Crear directorios si no existen
os.makedirs("uploaded_cvs", exist_ok=True)
os.makedirs("profile_pictures", exist_ok=True)
# ⭐ DIRECTORIOS TEMPORALES (ya existían)
os.makedirs("temp_files", exist_ok=True)  # Para archivos temporales
os.makedirs("temp_registrations", exist_ok=True)  # Para datos de registro temporal

app = FastAPI(
    title="UserAPI",
    description="API de usuarios con autenticación JWT y verificación de email temporal",
    version="1.0.0"
)

# ⭐ EVENTO DE STARTUP - Simplificado para versión de deployment
@app.on_event("startup")
async def startup_event():
    """Ejecutar tareas al iniciar la aplicación"""
    print("🚀 Iniciando UserAPI...")
    print("✅ UserAPI iniciada correctamente")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",  # Desarrollo local
        "https://frontend-qa-737714447258.us-central1.run.app",  # QA
        "https://frontend-737714447258.us-central1.run.app"  # Producción
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Servir archivos estáticos (CVs)
app.mount("/uploaded_cvs", StaticFiles(directory="uploaded_cvs"), name="uploaded_cvs")

# Servir fotos de perfil
app.mount("/profile_pictures", StaticFiles(directory="profile_pictures"), name="profile_pictures")

# Incluir las rutas
app.include_router(router, prefix="/api/v1", tags=["users"])

@app.get("/")
async def root():
    return {
        "message": "UserAPI está funcionando correctamente con verificación de email temporal",
        "version": "1.0.0",
        "features": [
            "Registro temporal con verificación de email",
            "Sin cuentas fantasma",
            "Archivos temporales hasta confirmación"
        ]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "email_verification": "enabled",
        "temporal_storage": "enabled",
        "cv_analyzer": "enabled"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)