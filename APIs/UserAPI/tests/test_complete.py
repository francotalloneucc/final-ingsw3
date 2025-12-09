"""
Test suite completo para UserAPI simplificada

Cubre:
- Registro (candidatos y empresas)
- Autenticación (login)
- Perfil de usuario
- Actualización de perfil
- Endpoints admin
- Gestión de recruiters
- Endpoint interno

Objetivo: >80% code coverage
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from main import app
from database import Base, get_db
from models import User, UserRoleEnum, CompanyRecruiter
from auth import create_access_token, get_password_hash


@pytest.fixture(scope="function")
def test_db():
    """Crea una base de datos SQLite temporal para tests"""
    db_fd, db_path = tempfile.mkstemp()
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(test_db):
    """Cliente de test con DB limpia"""
    return TestClient(app)


@pytest.fixture
def admin_token(client, test_db):
    """Crea un admin y retorna su token"""
    db = test_db()
    admin = User(
        email="admin@test.com",
        hashed_password=get_password_hash("AdminPass123!"),
        nombre="Admin",
        role=UserRoleEnum.admin,
        email_verified=True
    )
    db.add(admin)
    db.commit()
    db.close()

    token = create_access_token(data={"sub": "admin@test.com"})
    return token


# =====================================================
# TESTS DE HEALTH CHECK
# =====================================================

class TestHealthCheck:
    """Tests para health check endpoint"""

    def test_health_check(self, client):
        """
        GIVEN la API está corriendo
        WHEN se hace request a /health
        THEN retorna status healthy
        """
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "UserAPI"


# =====================================================
# TESTS DE REGISTRO
# =====================================================

class TestRegistro:
    """Tests para registro de usuarios"""

    def test_register_candidato_exitoso(self, client):
        """
        GIVEN datos válidos de candidato
        WHEN se registra
        THEN se crea el usuario exitosamente
        """
        response = client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        assert response.status_code == 200
        user = response.json()
        assert user["email"] == "candidato@test.com"
        assert user["nombre"] == "Juan"
        assert user["apellido"] == "Pérez"
        assert user["role"] == "candidato"
        assert user["verified"] is True

    def test_register_candidato_email_duplicado(self, client):
        """
        GIVEN un candidato ya registrado
        WHEN se intenta registrar con el mismo email
        THEN retorna error 400
        """
        # Registrar primero
        client.post("/api/v1/register-candidato", data={
            "email": "duplicate@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Intentar duplicar
        response = client.post("/api/v1/register-candidato", data={
            "email": "duplicate@test.com",
            "password": "TestPass123!",
            "nombre": "Maria",
            "apellido": "Lopez",
            "genero": "femenino",
            "fecha_nacimiento": "1992-05-15"
        })

        assert response.status_code == 400
        assert "ya está registrado" in response.json()["detail"]

    def test_register_empresa_exitoso(self, client):
        """
        GIVEN datos válidos de empresa
        WHEN se registra
        THEN se crea la empresa exitosamente
        """
        response = client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Tech Corp",
            "descripcion": "Empresa de tecnología"
        })

        assert response.status_code == 200
        user = response.json()
        assert user["email"] == "empresa@test.com"
        assert user["nombre"] == "Tech Corp"
        assert user["role"] == "empresa"
        assert user["descripcion"] == "Empresa de tecnología"
        assert user["verified"] is True

    def test_register_empresa_email_duplicado(self, client):
        """
        GIVEN una empresa ya registrada
        WHEN se intenta registrar con el mismo email
        THEN retorna error 400
        """
        # Registrar primero
        client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Tech Corp",
            "descripcion": "Tech company"
        })

        # Intentar duplicar
        response = client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Another Corp",
            "descripcion": "Another company"
        })

        assert response.status_code == 400
        assert "ya está registrado" in response.json()["detail"]

    def test_register_candidato_datos_invalidos(self, client):
        """
        GIVEN datos inválidos (nombre vacío)
        WHEN se intenta registrar
        THEN retorna error de validación
        """
        response = client.post("/api/v1/register-candidato", data={
            "email": "test@test.com",
            "password": "TestPass123!",
            "nombre": "",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        assert response.status_code == 422


# =====================================================
# TESTS DE AUTENTICACIÓN
# =====================================================

class TestAutenticacion:
    """Tests para login"""

    def test_login_candidato_exitoso(self, client):
        """
        GIVEN un candidato registrado
        WHEN hace login con credenciales correctas
        THEN recibe token válido
        """
        # Registrar candidato
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login
        response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "TestPass123!"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "candidato@test.com"

    def test_login_empresa_exitoso(self, client):
        """
        GIVEN una empresa registrada
        WHEN hace login con credenciales correctas
        THEN recibe token válido
        """
        # Registrar empresa
        client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Tech Corp",
            "descripcion": "Tech company"
        })

        # Login
        response = client.post("/api/v1/login", json={
            "email": "empresa@test.com",
            "password": "TestPass123!"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "empresa@test.com"

    def test_login_credenciales_incorrectas(self, client):
        """
        GIVEN un usuario registrado
        WHEN intenta login con password incorrecta
        THEN recibe error 401
        """
        # Registrar
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login con password incorrecta
        response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "WrongPassword!"
        })

        assert response.status_code == 401
        assert "Credenciales incorrectas" in response.json()["detail"]

    def test_login_usuario_inexistente(self, client):
        """
        GIVEN un email no registrado
        WHEN intenta login
        THEN recibe error 401
        """
        response = client.post("/api/v1/login", json={
            "email": "noexiste@test.com",
            "password": "TestPass123!"
        })

        assert response.status_code == 401


# =====================================================
# TESTS DE PERFIL
# =====================================================

class TestPerfil:
    """Tests para obtener y actualizar perfil"""

    def test_get_current_user_profile(self, client):
        """
        GIVEN un usuario autenticado
        WHEN solicita su perfil
        THEN recibe sus datos
        """
        # Registrar y login
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        login_response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        # Obtener perfil
        response = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        user = response.json()
        assert user["email"] == "candidato@test.com"
        assert user["nombre"] == "Juan"

    def test_get_profile_without_token(self, client):
        """
        GIVEN sin token de autenticación
        WHEN solicita perfil
        THEN recibe error 403 (Forbidden)
        """
        response = client.get("/api/v1/me")
        assert response.status_code == 403

    def test_update_candidato_profile(self, client):
        """
        GIVEN un candidato autenticado
        WHEN actualiza su perfil
        THEN los cambios se guardan
        """
        # Registrar y login
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        login_response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        # Actualizar perfil
        response = client.put(
            "/api/v1/me/candidato",
            data={
                "nombre": "Juan Carlos",
                "apellido": "González"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        user = response.json()
        assert user["nombre"] == "Juan Carlos"
        assert user["apellido"] == "González"

    def test_update_empresa_profile(self, client):
        """
        GIVEN una empresa autenticada
        WHEN actualiza su perfil
        THEN los cambios se guardan
        """
        # Registrar y login
        client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Tech Corp",
            "descripcion": "Original description"
        })

        login_response = client.post("/api/v1/login", json={
            "email": "empresa@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        # Actualizar perfil
        response = client.put(
            "/api/v1/me/empresa",
            data={
                "nombre": "Tech Corp International",
                "descripcion": "Updated description"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        user = response.json()
        assert user["nombre"] == "Tech Corp International"
        assert user["descripcion"] == "Updated description"

    def test_candidato_cannot_use_empresa_endpoint(self, client):
        """
        GIVEN un candidato
        WHEN intenta usar endpoint de empresa
        THEN recibe error 403
        """
        # Registrar candidato y login
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        login_response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        # Intentar actualizar como empresa
        response = client.put(
            "/api/v1/me/empresa",
            data={"nombre": "Hacker"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


# =====================================================
# TESTS DE ENDPOINTS ADMIN
# =====================================================

class TestAdmin:
    """Tests para endpoints administrativos"""

    def test_admin_get_all_users(self, client, admin_token):
        """
        GIVEN un admin autenticado y varios usuarios
        WHEN solicita todos los usuarios
        THEN recibe la lista completa
        """
        # Crear usuarios
        client.post("/api/v1/register-candidato", data={
            "email": "candidato1@test.com",
            "password": "TestPass123!",
            "nombre": "User1",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        client.post("/api/v1/register-empresa", data={
            "email": "empresa1@test.com",
            "password": "TestPass123!",
            "nombre": "Company1",
            "descripcion": "Test company"
        })

        # Obtener todos los usuarios
        response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 3  # admin + 2 usuarios creados

    def test_admin_get_all_candidates(self, client, admin_token):
        """
        GIVEN un admin autenticado y varios candidatos
        WHEN solicita todos los candidatos
        THEN recibe lista de candidatos
        """
        # Crear candidatos
        client.post("/api/v1/register-candidato", data={
            "email": "candidato1@test.com",
            "password": "TestPass123!",
            "nombre": "User1",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        client.post("/api/v1/register-candidato", data={
            "email": "candidato2@test.com",
            "password": "TestPass123!",
            "nombre": "User2",
            "apellido": "Test",
            "genero": "femenino",
            "fecha_nacimiento": "1995-05-15"
        })

        # Obtener candidatos
        response = client.get(
            "/api/v1/admin/candidates",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        candidates = response.json()
        assert len(candidates) >= 2
        assert all(candidate["role"] == "candidato" for candidate in candidates)

    def test_non_admin_cannot_access_admin_endpoints(self, client):
        """
        GIVEN un usuario no-admin
        WHEN intenta acceder a endpoints admin
        THEN recibe error 403
        """
        # Registrar candidato y login
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        login_response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        # Intentar acceder a endpoint admin
        response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


# =====================================================
# TESTS DE GESTIÓN DE RECRUITERS
# =====================================================

class TestRecruiters:
    """Tests para gestión de recruiters"""

    def test_empresa_add_recruiter(self, client, test_db):
        """
        GIVEN una empresa y un candidato
        WHEN la empresa asigna al candidato como recruiter
        THEN la relación se crea exitosamente
        """
        # Registrar empresa
        client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Tech Corp",
            "descripcion": "Tech company"
        })

        # Registrar candidato
        client.post("/api/v1/register-candidato", data={
            "email": "recruiter@test.com",
            "password": "TestPass123!",
            "nombre": "Recruiter",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login como empresa
        login_response = client.post("/api/v1/login", json={
            "email": "empresa@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        # Asignar recruiter
        response = client.post(
            "/api/v1/companies/add-recruiter",
            params={"recruiter_email": "recruiter@test.com"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert "asignado exitosamente" in response.json()["message"]

    def test_empresa_get_my_recruiters(self, client):
        """
        GIVEN una empresa con recruiters asignados
        WHEN solicita sus recruiters
        THEN recibe la lista
        """
        # Registrar empresa
        client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Tech Corp",
            "descripcion": "Tech company"
        })

        # Registrar candidato
        client.post("/api/v1/register-candidato", data={
            "email": "recruiter@test.com",
            "password": "TestPass123!",
            "nombre": "Recruiter",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login como empresa y asignar recruiter
        login_response = client.post("/api/v1/login", json={
            "email": "empresa@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        client.post(
            "/api/v1/companies/add-recruiter",
            params={"recruiter_email": "recruiter@test.com"},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Obtener recruiters
        response = client.get(
            "/api/v1/companies/my-recruiters",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        recruiters = response.json()
        assert len(recruiters) == 1
        assert recruiters[0]["email"] == "recruiter@test.com"

    def test_candidato_get_recruiting_for(self, client, test_db):
        """
        GIVEN un candidato asignado como recruiter de una empresa
        WHEN solicita las empresas donde es recruiter
        THEN recibe la lista
        """
        # Registrar empresa
        client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Tech Corp",
            "descripcion": "Tech company"
        })

        # Registrar candidato
        client.post("/api/v1/register-candidato", data={
            "email": "recruiter@test.com",
            "password": "TestPass123!",
            "nombre": "Recruiter",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login como empresa y asignar recruiter
        empresa_login = client.post("/api/v1/login", json={
            "email": "empresa@test.com",
            "password": "TestPass123!"
        })
        empresa_token = empresa_login.json()["access_token"]

        client.post(
            "/api/v1/companies/add-recruiter",
            params={"recruiter_email": "recruiter@test.com"},
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Login como recruiter y obtener empresas
        recruiter_login = client.post("/api/v1/login", json={
            "email": "recruiter@test.com",
            "password": "TestPass123!"
        })
        recruiter_token = recruiter_login.json()["access_token"]

        response = client.get(
            "/api/v1/me/recruiting-for",
            headers={"Authorization": f"Bearer {recruiter_token}"}
        )

        assert response.status_code == 200
        companies = response.json()
        assert len(companies) == 1
        assert companies[0]["email"] == "empresa@test.com"

    def test_empresa_remove_recruiter(self, client):
        """
        GIVEN una empresa con un recruiter asignado
        WHEN elimina al recruiter
        THEN la relación se elimina
        """
        # Registrar empresa
        client.post("/api/v1/register-empresa", data={
            "email": "empresa@test.com",
            "password": "TestPass123!",
            "nombre": "Tech Corp",
            "descripcion": "Tech company"
        })

        # Registrar candidato
        client.post("/api/v1/register-candidato", data={
            "email": "recruiter@test.com",
            "password": "TestPass123!",
            "nombre": "Recruiter",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login y asignar recruiter
        login_response = client.post("/api/v1/login", json={
            "email": "empresa@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        client.post(
            "/api/v1/companies/add-recruiter",
            params={"recruiter_email": "recruiter@test.com"},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Obtener ID del recruiter
        login_rec = client.post("/api/v1/login", json={
            "email": "recruiter@test.com",
            "password": "TestPass123!"
        })
        recruiter_id = login_rec.json()["user"]["id"]

        # Eliminar recruiter
        response = client.delete(
            "/api/v1/companies/remove-recruiter",
            params={"recruiter_id": recruiter_id},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert "eliminado exitosamente" in response.json()["message"]

    def test_candidato_cannot_add_recruiter(self, client):
        """
        GIVEN un candidato autenticado
        WHEN intenta asignar un recruiter
        THEN recibe error 403
        """
        # Registrar dos candidatos
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Candidato",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        client.post("/api/v1/register-candidato", data={
            "email": "recruiter@test.com",
            "password": "TestPass123!",
            "nombre": "Recruiter",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login como candidato
        login_response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "TestPass123!"
        })
        token = login_response.json()["access_token"]

        # Intentar asignar recruiter
        response = client.post(
            "/api/v1/companies/add-recruiter",
            params={"recruiter_email": "recruiter@test.com"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


# =====================================================
# TESTS DE ENDPOINT INTERNO
# =====================================================

class TestInternalEndpoint:
    """Tests para endpoint interno"""

    def test_get_user_internal_with_valid_api_key(self, client, test_db):
        """
        GIVEN un usuario existente y API key válida
        WHEN se solicita el usuario vía endpoint interno
        THEN retorna los datos del usuario
        """
        # Registrar usuario
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login para obtener ID
        login_response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "TestPass123!"
        })
        user_id = login_response.json()["user"]["id"]

        # Obtener usuario via endpoint interno
        import os
        api_key = os.getenv("INTERNAL_SERVICE_API_KEY", "internal-service-key-change-in-production")

        response = client.get(
            f"/api/v1/internal/users/{user_id}",
            headers={"X-Internal-Api-Key": api_key}
        )

        assert response.status_code == 200
        user = response.json()
        assert user["email"] == "candidato@test.com"
        assert user["nombre"] == "Juan"

    def test_get_user_internal_with_invalid_api_key(self, client, test_db):
        """
        GIVEN un usuario existente y API key inválida
        WHEN se intenta acceder al endpoint interno
        THEN recibe error 403
        """
        # Registrar usuario
        client.post("/api/v1/register-candidato", data={
            "email": "candidato@test.com",
            "password": "TestPass123!",
            "nombre": "Juan",
            "apellido": "Pérez",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Login para obtener ID
        login_response = client.post("/api/v1/login", json={
            "email": "candidato@test.com",
            "password": "TestPass123!"
        })
        user_id = login_response.json()["user"]["id"]

        # Intentar acceder con API key inválida
        response = client.get(
            f"/api/v1/internal/users/{user_id}",
            headers={"X-Internal-Api-Key": "invalid-key"}
        )

        assert response.status_code == 403

    def test_get_user_internal_nonexistent_user(self, client):
        """
        GIVEN un ID que no existe
        WHEN se solicita via endpoint interno
        THEN retorna error 404
        """
        import os
        api_key = os.getenv("INTERNAL_SERVICE_API_KEY", "internal-service-key-change-in-production")

        response = client.get(
            "/api/v1/internal/users/99999",
            headers={"X-Internal-Api-Key": api_key}
        )

        assert response.status_code == 404
