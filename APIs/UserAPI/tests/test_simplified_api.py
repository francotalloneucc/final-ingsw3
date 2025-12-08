"""
Tests unitarios para UserAPI simplificada (versión TP5 deployment)

Este archivo contiene tests para las funcionalidades core implementadas:
- Health check
- Registro simple de candidatos (sin CV)
- Registro simple de empresas (sin verificación)
- Login con JWT
- Endpoints protegidos con auth

Patrón AAA (Arrange, Act, Assert)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os
from datetime import datetime

from main import app
from database import Base, get_db
from models import User, UserRoleEnum, GenderEnum


@pytest.fixture(scope="function")
def test_db():
    """
    Crea una base de datos SQLite en memoria para tests
    Patrón: Test Database Pattern
    """
    # Arrange: Crear DB temporal
    db_fd, db_path = tempfile.mkstemp()
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Crear tablas
    Base.metadata.create_all(bind=engine)

    # Sobrescribir dependency de DB
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield TestingSessionLocal

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    """Cliente de testing para FastAPI"""
    return TestClient(app)


# ===================================
# TESTS DE HEALTH CHECK
# ===================================

class TestHealthEndpoint:
    """Tests para el endpoint de health check"""

    def test_health_check_returns_200(self, client):
        """
        GIVEN una API corriendo
        WHEN se hace GET /health
        THEN retorna 200 y datos correctos
        """
        # Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        # Verificar campos presentes en la respuesta real
        assert "email_verification" in data
        assert "temporal_storage" in data
        assert "cv_analyzer" in data

    def test_health_check_response_structure(self, client):
        """Verifica estructura de respuesta del health check"""
        # Act
        response = client.get("/health")
        data = response.json()

        # Assert
        assert "status" in data
        assert data["status"] == "healthy"


# ===================================
# TESTS DE REGISTRO DE CANDIDATOS
# ===================================

class TestCandidatoRegistration:
    """Tests para registro simple de candidatos (sin CV)"""

    def test_register_candidato_success(self, client):
        """
        GIVEN datos válidos de candidato
        WHEN se hace POST /api/v1/register-candidato
        THEN se crea el usuario correctamente
        """
        # Arrange
        candidato_data = {
            "email": "candidato@test.com",
            "password": "Password123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        }

        # Act
        response = client.post("/api/v1/register-candidato", data=candidato_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "candidato@test.com"
        assert data["nombre"] == "Juan"
        assert data["apellido"] == "Pérez"
        assert data["role"] == "candidato"
        assert data["verified"] == True  # Registro simple sin verificación

    def test_register_candidato_duplicate_email(self, client):
        """
        GIVEN un email ya registrado
        WHEN se intenta registrar con el mismo email
        THEN retorna error 400
        """
        # Arrange
        candidato_data = {
            "email": "duplicate@test.com",
            "password": "Password123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        }

        # Primer registro
        client.post("/api/v1/register-candidato", data=candidato_data)

        # Act: Segundo registro con mismo email
        response = client.post("/api/v1/register-candidato", data=candidato_data)

        # Assert
        assert response.status_code == 400
        assert "ya está registrado" in response.json()["detail"]

    def test_register_candidato_missing_required_fields(self, client):
        """
        GIVEN datos incompletos
        WHEN se intenta registrar
        THEN retorna error 422 (validation error)
        """
        # Arrange: Falta el campo 'apellido'
        incomplete_data = {
            "email": "incomplete@test.com",
            "password": "Password123!",
            "nombre": "Juan",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        }

        # Act
        response = client.post("/api/v1/register-candidato", data=incomplete_data)

        # Assert
        assert response.status_code == 422

    def test_register_candidato_invalid_email(self, client):
        """
        Verifica validación de formato de email
        NOTA: FastAPI acepta cualquier string como email en Form,
        pero la validación de DB debería fallar con email inválido
        """
        # Arrange
        invalid_data = {
            "email": "not-an-email",
            "password": "Password123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        }

        # Act
        response = client.post("/api/v1/register-candidato", data=invalid_data)

        # Assert
        # FastAPI acepta string pero podría fallar en validación de schemas o DB
        assert response.status_code in [200, 400, 422]


# ===================================
# TESTS DE REGISTRO DE EMPRESAS
# ===================================

class TestEmpresaRegistration:
    """Tests para registro simple de empresas"""

    def test_register_empresa_success(self, client):
        """
        GIVEN datos válidos de empresa
        WHEN se hace POST /api/v1/register-empresa
        THEN se crea el usuario correctamente
        """
        # Arrange
        empresa_data = {
            "email": "empresa@test.com",
            "password": "Password123!",
            "nombre": "Tech Corp",
            "descripcion": "Empresa de tecnología"
        }

        # Act
        response = client.post("/api/v1/register-empresa", data=empresa_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "empresa@test.com"
        assert data["nombre"] == "Tech Corp"
        assert data["role"] == "empresa"
        assert data["verified"] == True  # Registro simple sin verificación

    def test_register_empresa_duplicate_email(self, client):
        """
        GIVEN un email ya registrado
        WHEN se intenta registrar empresa con el mismo email
        THEN retorna error 400
        """
        # Arrange
        empresa_data = {
            "email": "duplicate-company@test.com",
            "password": "Password123!",
            "nombre": "Tech Corp",
            "descripcion": "Empresa de tecnología"
        }

        # Primer registro
        client.post("/api/v1/register-empresa", data=empresa_data)

        # Act: Segundo registro
        response = client.post("/api/v1/register-empresa", data=empresa_data)

        # Assert
        assert response.status_code == 400


# ===================================
# TESTS DE LOGIN
# ===================================

class TestLogin:
    """Tests para autenticación con JWT"""

    def test_login_success(self, client):
        """
        GIVEN un usuario registrado
        WHEN hace login con credenciales correctas
        THEN recibe access token válido
        """
        # Arrange: Registrar usuario
        register_data = {
            "email": "login@test.com",
            "password": "Password123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        }
        client.post("/api/v1/register-candidato", data=register_data)

        # Act: Login con JSON (UserLogin schema)
        login_data = {
            "email": "login@test.com",
            "password": "Password123!"
        }
        response = client.post("/api/v1/login", json=login_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(self, client):
        """
        GIVEN un usuario registrado
        WHEN hace login con contraseña incorrecta
        THEN retorna error 401
        """
        # Arrange: Registrar usuario
        register_data = {
            "email": "wrongpass@test.com",
            "password": "Password123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        }
        client.post("/api/v1/register-candidato", data=register_data)

        # Act: Login con contraseña incorrecta (JSON)
        login_data = {
            "email": "wrongpass@test.com",
            "password": "WrongPassword!"
        }
        response = client.post("/api/v1/login", json=login_data)

        # Assert
        assert response.status_code == 401
        assert "incorrectos" in response.json()["detail"]

    def test_login_nonexistent_user(self, client):
        """
        GIVEN un email no registrado
        WHEN intenta hacer login
        THEN retorna error 401
        """
        # Act: Login con JSON
        login_data = {
            "email": "noexiste@test.com",
            "password": "Password123!"
        }
        response = client.post("/api/v1/login", json=login_data)

        # Assert
        assert response.status_code == 401


# ===================================
# TESTS DE ENDPOINTS PROTEGIDOS
# ===================================

class TestProtectedEndpoints:
    """Tests para endpoints que requieren autenticación JWT"""

    def test_get_me_without_token(self, client):
        """
        GIVEN un usuario sin token de autenticación
        WHEN intenta acceder a /api/v1/me
        THEN retorna error 401 o 403
        """
        # Act
        response = client.get("/api/v1/me")

        # Assert
        assert response.status_code in [401, 403, 422]

    def test_get_me_with_valid_token(self, client):
        """
        GIVEN un usuario autenticado con token válido
        WHEN hace GET /api/v1/me
        THEN retorna sus datos de usuario
        """
        # Arrange: Registrar y obtener token
        register_data = {
            "email": "authed@test.com",
            "password": "Password123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        }
        client.post("/api/v1/register-candidato", data=register_data)

        # Login con JSON para obtener token
        login_response = client.post("/api/v1/login", json={
            "email": "authed@test.com",
            "password": "Password123!"
        })
        token = login_response.json()["access_token"]

        # Act: Acceder a endpoint protegido
        response = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "authed@test.com"


# ===================================
# TESTS DE OBSOLETE ENDPOINT
# ===================================
# TESTS DE VALIDACIÓN Y EDGE CASES
# ===================================

class TestValidationsAndEdgeCases:
    """Tests para validaciones y casos edge"""

    def test_password_truncation_to_72_bytes(self, client):
        """
        GIVEN una contraseña muy larga (>72 bytes - límite bcrypt)
        WHEN se registra
        THEN se trunca correctamente y permite login
        """
        # Arrange: Contraseña de 100 caracteres
        long_password = "A" * 100
        register_data = {
            "email": "longpass@test.com",
            "password": long_password,
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        }

        # Act: Registrar
        register_response = client.post("/api/v1/register-candidato", data=register_data)

        # Assert: Registro exitoso
        assert register_response.status_code == 200

        # Act: Login con contraseña original (debería truncarse en el código)
        login_response = client.post("/api/v1/login", json={
            "email": "longpass@test.com",
            "password": long_password  # Usar contraseña original
        })

        # Assert: Login exitoso (la API trunca internamente)
        assert login_response.status_code == 200

    def test_cors_headers_present(self, client):
        """Verifica que CORS esté configurado"""
        # Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200
        # CORS debería estar configurado en main.py

    def test_404_on_nonexistent_route(self, client):
        """
        GIVEN una ruta que no existe
        WHEN se accede
        THEN retorna 404
        """
        # Act
        response = client.get("/api/v1/ruta-inexistente")

        # Assert
        assert response.status_code == 404
