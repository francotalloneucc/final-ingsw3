"""
Tests adicionales para mejorar coverage del UserAPI
Tests para funcionalidades de admin, recruiters, y edge cases

Objetivo: Alcanzar 70%+ de code coverage
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from main import app
from database import Base, get_db
from models import User, UserRoleEnum
from auth import create_access_token


@pytest.fixture(scope="function")
def test_db():
    """Crea una base de datos SQLite en memoria para tests"""
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
    """Crea cliente de test con DB limpia"""
    return TestClient(app)


@pytest.fixture
def admin_token(client, test_db):
    """Crea un admin y retorna su token"""
    # Crear admin manualmente en DB
    from models import User
    from auth import get_password_hash

    db = test_db()
    admin = User(
        email="admin@test.com",
        hashed_password=get_password_hash("AdminPass123!"),
        nombre="Admin",
        role=UserRoleEnum.admin,
        verified=True,
        email_verified=True
    )
    db.add(admin)
    db.commit()
    db.close()

    # Generar token
    token = create_access_token(data={"sub": "admin@test.com"})
    return token


@pytest.fixture
def empresa_token(client):
    """Crea una empresa y retorna su token"""
    # Registrar empresa
    empresa_data = {
        "email": "empresa@test.com",
        "password": "EmpresaPass123!",
        "nombre": "Tech Corp",
        "descripcion": "Empresa de tecnología"
    }
    client.post("/api/v1/register-empresa", data=empresa_data)

    # Login
    login_response = client.post("/api/v1/login", json={
        "email": "empresa@test.com",
        "password": "EmpresaPass123!"
    })
    token = login_response.json()["access_token"]
    return token


@pytest.fixture
def candidato_token(client):
    """Crea un candidato y retorna su token"""
    # Registrar candidato
    candidato_data = {
        "email": "candidato@test.com",
        "password": "CandidatoPass123!",
        "nombre": "Juan",
        "apellido": "Pérez",
        "genero": "masculino",
        "fecha_nacimiento": "1990-01-01"
    }
    client.post("/api/v1/register-candidato", data=candidato_data)

    # Login
    login_response = client.post("/api/v1/login", json={
        "email": "candidato@test.com",
        "password": "CandidatoPass123!"
    })
    token = login_response.json()["access_token"]
    return token


# ===================================
# TESTS DE FUNCIONALIDADES ADMIN
# ===================================

class TestAdminEndpoints:
    """Tests para endpoints administrativos"""

    def test_get_all_users_as_admin(self, client, admin_token):
        """
        GIVEN usuarios registrados
        WHEN admin solicita todos los usuarios
        THEN recibe la lista completa
        """
        # Arrange: Crear algunos usuarios
        client.post("/api/v1/register-candidato", data={
            "email": "user1@test.com",
            "password": "Pass123!",
            "nombre": "User",
            "apellido": "One",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        client.post("/api/v1/register-empresa", data={
            "email": "company1@test.com",
            "password": "Pass123!",
            "nombre": "Company One",
            "descripcion": "Test company"
        })

        # Act
        response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Assert
        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 3  # admin + 2 usuarios creados

    def test_get_unverified_companies(self, client, admin_token):
        """
        GIVEN empresas sin verificar
        WHEN admin solicita empresas pendientes
        THEN recibe solo empresas no verificadas
        """
        # Arrange: Crear empresa (por defecto no verificada)
        client.post("/api/v1/register-empresa", data={
            "email": "unverified@test.com",
            "password": "Pass123!",
            "nombre": "Unverified Co",
            "descripcion": "Pending verification"
        })

        # Act
        response = client.get(
            "/api/v1/admin/companies/pending",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Assert
        assert response.status_code == 200
        companies = response.json()
        assert len(companies) >= 1
        assert all(not company["verified"] for company in companies)

    def test_verify_company_by_email(self, client, admin_token):
        """
        GIVEN una empresa sin verificar
        WHEN admin verifica la empresa
        THEN la empresa queda verificada
        """
        # Arrange: Crear empresa
        client.post("/api/v1/register-empresa", data={
            "email": "toverify@test.com",
            "password": "Pass123!",
            "nombre": "To Verify Co",
            "descripcion": "Will be verified"
        })

        # Act: Verificar empresa
        response = client.put(
            "/api/v1/admin/companies/verify-by-email",
            json={"email": "toverify@test.com"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Assert
        assert response.status_code == 200
        company = response.json()
        assert company["verified"] is True

    def test_get_all_candidates(self, client, admin_token):
        """
        GIVEN candidatos registrados
        WHEN admin solicita todos los candidatos
        THEN recibe lista de candidatos
        """
        # Arrange
        client.post("/api/v1/register-candidato", data={
            "email": "candidate@test.com",
            "password": "Pass123!",
            "nombre": "Jane",
            "apellido": "Doe",
            "genero": "femenino",
            "fecha_nacimiento": "1995-05-15"
        })

        # Act
        response = client.get(
            "/api/v1/admin/candidates",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Assert
        assert response.status_code == 200
        candidates = response.json()
        assert len(candidates) >= 1
        assert all(candidate["role"] == "candidato" for candidate in candidates)

    def test_non_admin_cannot_access_admin_endpoints(self, client, candidato_token):
        """
        GIVEN un usuario no-admin
        WHEN intenta acceder a endpoints admin
        THEN recibe error 403 Forbidden
        """
        # Act
        response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {candidato_token}"}
        )

        # Assert
        assert response.status_code == 403


# ===================================
# TESTS DE GESTIÓN DE RECRUITERS
# ===================================

class TestRecruiterManagement:
    """Tests para asignación y gestión de recruiters"""

    def test_empresa_add_recruiter(self, client, empresa_token, candidato_token, test_db):
        """
        GIVEN una empresa y un candidato
        WHEN empresa agrega candidato como recruiter
        THEN el candidato aparece en la lista de recruiters
        """
        # Act: Agregar recruiter
        response = client.post(
            "/api/v1/companies/add-recruiter",
            json={"recruiter_email": "candidato@test.com"},
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Assert
        assert response.status_code == 200
        assert "agregado como recruiter" in response.json()["message"]

    def test_empresa_get_my_recruiters(self, client, empresa_token):
        """
        GIVEN una empresa con recruiters
        WHEN solicita su lista de recruiters
        THEN recibe todos sus recruiters
        """
        # Arrange: Crear candidato y agregarlo como recruiter
        client.post("/api/v1/register-candidato", data={
            "email": "recruiter1@test.com",
            "password": "Pass123!",
            "nombre": "Rec",
            "apellido": "One",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        client.post(
            "/api/v1/companies/add-recruiter",
            json={"recruiter_email": "recruiter1@test.com"},
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Act
        response = client.get(
            "/api/v1/companies/my-recruiters",
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Assert
        assert response.status_code == 200
        recruiters = response.json()["recruiters"]
        assert len(recruiters) >= 1

    def test_empresa_remove_recruiter(self, client, empresa_token):
        """
        GIVEN una empresa con un recruiter
        WHEN empresa remueve el recruiter
        THEN el recruiter ya no aparece en la lista
        """
        # Arrange: Agregar recruiter
        client.post("/api/v1/register-candidato", data={
            "email": "toremove@test.com",
            "password": "Pass123!",
            "nombre": "To",
            "apellido": "Remove",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        client.post(
            "/api/v1/companies/add-recruiter",
            json={"recruiter_email": "toremove@test.com"},
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Act: Remover recruiter
        response = client.delete(
            "/api/v1/companies/remove-recruiter",
            json={"recruiter_email": "toremove@test.com"},
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Assert
        assert response.status_code == 200
        assert "removido" in response.json()["message"].lower()

    def test_recruiter_get_recruiting_companies(self, client, empresa_token, candidato_token):
        """
        GIVEN un candidato asignado como recruiter
        WHEN solicita empresas donde es recruiter
        THEN recibe la lista de empresas
        """
        # Arrange: Agregar como recruiter
        client.post(
            "/api/v1/companies/add-recruiter",
            json={"recruiter_email": "candidato@test.com"},
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Act: Obtener empresas donde es recruiter
        response = client.get(
            "/api/v1/me/recruiting-for",
            headers={"Authorization": f"Bearer {candidato_token}"}
        )

        # Assert
        assert response.status_code == 200
        companies = response.json()["companies"]
        assert len(companies) >= 1

    def test_add_nonexistent_recruiter_fails(self, client, empresa_token):
        """
        GIVEN un email que no existe
        WHEN empresa intenta agregarlo como recruiter
        THEN recibe error 404
        """
        # Act
        response = client.post(
            "/api/v1/companies/add-recruiter",
            json={"recruiter_email": "noexiste@test.com"},
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Assert
        assert response.status_code == 404


# ===================================
# TESTS DE ACTUALIZACIÓN DE PERFIL
# ===================================

class TestProfileUpdate:
    """Tests para actualización de perfiles de usuario"""

    def test_update_candidato_profile(self, client, candidato_token):
        """
        GIVEN un candidato autenticado
        WHEN actualiza su perfil
        THEN los cambios se guardan correctamente
        """
        # Act
        response = client.put(
            "/api/v1/me/candidato",
            data={
                "nombre": "Juan Carlos",
                "apellido": "González"
            },
            headers={"Authorization": f"Bearer {candidato_token}"}
        )

        # Assert
        assert response.status_code == 200
        user = response.json()
        assert user["nombre"] == "Juan Carlos"
        assert user["apellido"] == "González"

    def test_update_empresa_profile(self, client, empresa_token):
        """
        GIVEN una empresa autenticada
        WHEN actualiza su perfil
        THEN los cambios se guardan correctamente
        """
        # Act
        response = client.put(
            "/api/v1/me/empresa",
            data={
                "nombre": "Tech Corp International",
                "descripcion": "Updated description"
            },
            headers={"Authorization": f"Bearer {empresa_token}"}
        )

        # Assert
        assert response.status_code == 200
        user = response.json()
        assert user["nombre"] == "Tech Corp International"
        assert user["descripcion"] == "Updated description"

    def test_candidato_cannot_use_empresa_endpoint(self, client, candidato_token):
        """
        GIVEN un candidato
        WHEN intenta usar endpoint de actualización de empresa
        THEN recibe error 403
        """
        # Act
        response = client.put(
            "/api/v1/me/empresa",
            data={"nombre": "Hacker"},
            headers={"Authorization": f"Bearer {candidato_token}"}
        )

        # Assert
        assert response.status_code == 403


# ===================================
# TESTS DE ENDPOINT INTERNO
# ===================================

class TestInternalEndpoints:
    """Tests para endpoints internos (comunicación entre APIs)"""

    def test_internal_get_user_by_id(self, client, candidato_token, test_db):
        """
        GIVEN un usuario registrado
        WHEN otro servicio solicita datos por ID interno
        THEN recibe datos completos del usuario
        """
        # Arrange: Obtener ID del candidato
        me_response = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {candidato_token}"}
        )
        user_id = me_response.json()["id"]

        # Act: Llamar endpoint interno (simular llamada desde JobsAPI)
        response = client.get(f"/api/v1/internal/users/{user_id}")

        # Assert
        assert response.status_code == 200
        user = response.json()
        assert user["id"] == user_id
        assert "cv_analizado" in user  # Datos completos incluyendo CV analizado

    def test_internal_get_nonexistent_user(self, client):
        """
        GIVEN un ID que no existe
        WHEN servicio interno solicita usuario
        THEN recibe error 404
        """
        # Act
        response = client.get("/api/v1/internal/users/99999")

        # Assert
        assert response.status_code == 404


# ===================================
# TESTS DE EDGE CASES
# ===================================

class TestEdgeCases:
    """Tests para casos límite y validaciones"""

    def test_register_with_empty_nombre(self, client):
        """
        GIVEN un nombre vacío
        WHEN se intenta registrar
        THEN recibe error de validación
        """
        # Act
        response = client.post("/api/v1/register-candidato", data={
            "email": "test@test.com",
            "password": "Pass123!",
            "nombre": "",
            "apellido": "Test",
            "genero": "masculino",
            "fecha_nacimiento": "1990-01-01"
        })

        # Assert
        assert response.status_code == 422  # Validation error

    def test_register_with_invalid_date(self, client):
        """
        GIVEN una fecha inválida
        WHEN se intenta registrar
        THEN recibe error de validación
        """
        # Act
        response = client.post("/api/v1/register-candidato", data={
            "email": "test@test.com",
            "password": "Pass123!",
            "nombre": "Test",
            "apellido": "User",
            "genero": "masculino",
            "fecha_nacimiento": "fecha-invalida"
        })

        # Assert
        assert response.status_code == 422

    def test_get_users_with_pagination(self, client, admin_token):
        """
        GIVEN múltiples usuarios
        WHEN admin solicita con paginación
        THEN recibe subset correcto
        """
        # Arrange: Crear varios usuarios
        for i in range(5):
            client.post("/api/v1/register-candidato", data={
                "email": f"user{i}@test.com",
                "password": "Pass123!",
                "nombre": f"User{i}",
                "apellido": "Test",
                "genero": "masculino",
                "fecha_nacimiento": "1990-01-01"
            })

        # Act
        response = client.get(
            "/api/v1/admin/users?skip=0&limit=3",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Assert
        assert response.status_code == 200
        users = response.json()
        assert len(users) <= 3  # Respeta el límite

    def test_update_nonexistent_user_fails(self, client, admin_token):
        """
        GIVEN un ID que no existe
        WHEN admin intenta actualizar
        THEN recibe error 404
        """
        # Act
        response = client.put(
            "/api/v1/users/99999",
            data={"nombre": "NonExistent"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Assert
        assert response.status_code == 404
