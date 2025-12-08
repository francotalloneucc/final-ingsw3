# Job Application Platform - TP5 Final IngSw3

Plataforma de aplicación de empleos construida con Angular 19 + FastAPI, desplegada en Google Cloud Platform con CI/CD mediante GitHub Actions.

## 📋 Tabla de Contenidos
- [Descripción](#descripción)
- [Arquitectura](#arquitectura)
- [URLs de Despliegue](#urls-de-despliegue)
- [Tecnologías](#tecnologías)
- [Requisitos Previos](#requisitos-previos)
- [Configuración Local](#configuración-local)
- [Deployment en GCP](#deployment-en-gcp)
- [CI/CD Pipeline](#cicd-pipeline)
- [Ambientes](#ambientes)
- [Documentación Adicional](#documentación-adicional)

---

## 🎯 Descripción

Sistema simplificado de gestión de empleos que permite:
- 👤 **Candidatos**: Registrarse, gestionar perfil
- 🏢 **Empresas**: Registrarse, gestionar perfil
- 🔐 **Autenticación**: JWT-based con roles (candidato, empresa, admin)

**Nota**: Versión simplificada para TP5 - sin upload de CV ni verificación de email.

---

## 🏗️ Arquitectura

### Componentes Desplegados
```
┌─────────────────────────────────────────┐
│         Google Cloud Platform           │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────┐   ┌────────────────┐ │
│  │ Cloud Run    │   │  Cloud Run     │ │
│  │              │   │                │ │
│  │  UserAPI     │◄──┤  Frontend      │ │
│  │  (FastAPI)   │   │  (Angular 19)  │ │
│  └──────┬───────┘   └────────────────┘ │
│         │                               │
│         ▼                               │
│  ┌──────────────┐                      │
│  │  Cloud SQL   │                      │
│  │  PostgreSQL  │                      │
│  └──────────────┘                      │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │     Secret Manager               │  │
│  │  - DATABASE_URL                  │  │
│  │  - SECRET_KEY (JWT)              │  │
│  │  - API Keys                      │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Ambientes

| Ambiente | UserAPI | Frontend | Base de Datos |
|----------|---------|----------|---------------|
| **QA** | `userapi-qa` | `frontend-qa` | Cloud SQL (shared) |
| **Production** | `userapi` | `frontend` | Cloud SQL (shared) |

---

## 🌐 URLs de Despliegue

### Producción
- **Frontend**: https://frontend-737714447258.us-central1.run.app
- **UserAPI**: https://userapi-737714447258.us-central1.run.app
- **API Docs**: https://userapi-737714447258.us-central1.run.app/docs

### QA (Testing)
- **Frontend QA**: https://frontend-qa-737714447258.us-central1.run.app
- **UserAPI QA**: https://userapi-qa-737714447258.us-central1.run.app
- **API Docs QA**: https://userapi-qa-737714447258.us-central1.run.app/docs

### Health Checks
- **Production**: https://userapi-737714447258.us-central1.run.app/health
- **QA**: https://userapi-qa-737714447258.us-central1.run.app/health

---

## 🛠️ Tecnologías

### Backend (UserAPI)
- **Framework**: FastAPI 0.104.1
- **Base de Datos**: PostgreSQL (Cloud SQL)
- **ORM**: SQLAlchemy 2.0.23
- **Autenticación**: JWT (python-jose)
- **Password Hashing**: bcrypt 4.0.1 + passlib
- **Validación**: Pydantic 2.5.0

### Frontend
- **Framework**: Angular 19
- **Language**: TypeScript 5.7
- **Styling**: Bootstrap 5.3 + Angular Material
- **HTTP Client**: Angular HttpClient
- **Routing**: Angular Router

### DevOps
- **Cloud Provider**: Google Cloud Platform
- **Hosting**: Cloud Run (serverless containers)
- **Database**: Cloud SQL PostgreSQL
- **Secrets**: Secret Manager
- **Container Registry**: Google Container Registry (GCR)
- **CI/CD**: GitHub Actions
- **Version Control**: Git + GitHub

---

## ✅ Requisitos Previos

### Para Desarrollo Local
- **Node.js** 20.x o superior
- **Python** 3.11 o superior
- **PostgreSQL** 14+ (local o Cloud SQL)
- **Docker** (opcional, para build local)
- **Google Cloud SDK** (para deployment)

### Para CI/CD
- Cuenta de **Google Cloud Platform** con créditos activos
- Cuenta de **GitHub** con permisos de admin en el repositorio
- **Service Account Key** de GCP con permisos necesarios

---

## 💻 Configuración Local

### 1. Clonar el Repositorio
```bash
git clone https://github.com/francotalloneucc/final-ingsw3.git
cd final-ingsw3
```

### 2. Backend (UserAPI)

#### Crear entorno virtual
```bash
cd APIs/UserAPI
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

#### Instalar dependencias
```bash
pip install -r requirements.txt
```

#### Configurar variables de entorno
Crear archivo `.env` en `APIs/UserAPI/`:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/userapi
SECRET_KEY=your-super-secret-jwt-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
INTERNAL_SERVICE_API_KEY=internal-key-change-this
```

#### Ejecutar servidor
```bash
python main.py
# Servidor corriendo en http://localhost:8000
# Docs en http://localhost:8000/docs
```

### 3. Frontend

#### Instalar dependencias
```bash
cd tf-frontend
npm install
```

#### Configurar environment (desarrollo)
El archivo `src/environments/environment.ts` ya está configurado:
```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api/v1'
};
```

#### Ejecutar servidor de desarrollo
```bash
npm start
# o
ng serve

# Aplicación corriendo en http://localhost:4200
```

---

## ☁️ Deployment en GCP

### Configuración Inicial (Una sola vez)

#### 1. Crear Proyecto GCP
```bash
gcloud projects create final-ingsoft3-2025-480515
gcloud config set project final-ingsoft3-2025-480515
```

#### 2. Habilitar APIs necesarias
```bash
gcloud services enable run.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

#### 3. Crear Instancia Cloud SQL
```bash
gcloud sql instances create userapi-db \
  --database-version=POSTGRES_14 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password=YOUR_STRONG_PASSWORD
```

#### 4. Crear Base de Datos
```bash
gcloud sql databases create userapi --instance=userapi-db
```

#### 5. Configurar Secrets en Secret Manager
```bash
# DATABASE_URL
echo -n "postgresql://postgres:PASSWORD@/userapi?host=/cloudsql/final-ingsoft3-2025-480515:us-central1:userapi-db" | \
  gcloud secrets create DATABASE_URL --data-file=-

# SECRET_KEY (generar uno aleatorio)
echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create SECRET_KEY --data-file=-

# INTERNAL_SERVICE_API_KEY
echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create INTERNAL_SERVICE_API_KEY --data-file=-

# EMAIL_USER y EMAIL_PASSWORD
echo -n "your-email@gmail.com" | \
  gcloud secrets create EMAIL_USER --data-file=-
echo -n "your-app-password" | \
  gcloud secrets create EMAIL_PASSWORD --data-file=-
```

#### 6. Crear Service Account
```bash
gcloud iam service-accounts create userapi-service-account \
  --display-name="UserAPI Service Account"

# Otorgar permisos
gcloud projects add-iam-policy-binding final-ingsoft3-2025-480515 \
  --member="serviceAccount:userapi-service-account@final-ingsoft3-2025-480515.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding final-ingsoft3-2025-480515 \
  --member="serviceAccount:userapi-service-account@final-ingsoft3-2025-480515.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Deployment Manual

#### Deploy UserAPI (Production)
```bash
cd APIs/UserAPI

# Build y push imagen
gcloud builds submit --tag gcr.io/final-ingsoft3-2025-480515/userapi:latest

# Deploy a Cloud Run
gcloud run deploy userapi \
  --image gcr.io/final-ingsoft3-2025-480515/userapi:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "API_PORT=8000" \
  --add-cloudsql-instances final-ingsoft3-2025-480515:us-central1:userapi-db \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,EMAIL_USER=EMAIL_USER:latest,EMAIL_PASSWORD=EMAIL_PASSWORD:latest,INTERNAL_SERVICE_API_KEY=INTERNAL_SERVICE_API_KEY:latest" \
  --service-account userapi-service-account@final-ingsoft3-2025-480515.iam.gserviceaccount.com
```

#### Deploy Frontend (Production)
```bash
cd tf-frontend

# Build y push imagen
gcloud builds submit --tag gcr.io/final-ingsoft3-2025-480515/frontend:latest

# Deploy a Cloud Run
gcloud run deploy frontend \
  --image gcr.io/final-ingsoft3-2025-480515/frontend:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated
```

#### Deploy QA (Similar, cambiar nombres)
Reemplazar `userapi` por `userapi-qa` y `frontend` por `frontend-qa`.

---

## 🚀 CI/CD Pipeline

### Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflow                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Push to main branch                                        │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────┐          │
│  │  BUILD STAGE                                 │          │
│  │  ┌────────────────┐  ┌──────────────────┐   │          │
│  │  │ Build UserAPI  │  │ Build Frontend   │   │          │
│  │  │   (Docker)     │  │  QA + Production │   │          │
│  │  └────────────────┘  └──────────────────┘   │          │
│  └──────────────────────────────────────────────┘          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────┐          │
│  │  DEPLOY QA                                   │          │
│  │  ┌────────────────┐  ┌──────────────────┐   │          │
│  │  │ Deploy UserAPI │  │ Deploy Frontend  │   │          │
│  │  │      QA        │  │       QA         │   │          │
│  │  └────────────────┘  └──────────────────┘   │          │
│  │  ┌────────────────────────────────────────┐ │          │
│  │  │ Health Checks                          │ │          │
│  │  └────────────────────────────────────────┘ │          │
│  └──────────────────────────────────────────────┘          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────┐          │
│  │  MANUAL APPROVAL                             │          │
│  │  (GitHub Environment Protection)             │          │
│  └──────────────────────────────────────────────┘          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────┐          │
│  │  DEPLOY PRODUCTION                           │          │
│  │  ┌────────────────┐  ┌──────────────────┐   │          │
│  │  │ Deploy UserAPI │  │ Deploy Frontend  │   │          │
│  │  │   Production   │  │   Production     │   │          │
│  │  └────────────────┘  └──────────────────┘   │          │
│  │  ┌────────────────────────────────────────┐ │          │
│  │  │ Health Checks                          │ │          │
│  │  └────────────────────────────────────────┘ │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Configuración del Pipeline

#### 1. Crear Service Account Key para GitHub Actions
```bash
# Crear key en formato JSON
gcloud iam service-accounts keys create gcp-key.json \
  --iam-account=userapi-service-account@final-ingsoft3-2025-480515.iam.gserviceaccount.com

# Copiar contenido del archivo (se usará en GitHub Secrets)
cat gcp-key.json
```

#### 2. Configurar GitHub Secrets
Ir a **GitHub Repository → Settings → Secrets and variables → Actions** y crear:

| Secret Name | Valor |
|-------------|-------|
| `GCP_SA_KEY` | Contenido completo del archivo `gcp-key.json` |

#### 3. Configurar GitHub Environments
Ir a **GitHub Repository → Settings → Environments**:

##### Environment: `qa`
- **Deployment branches**: `main`
- **Protection rules**: Ninguna (deploy automático)

##### Environment: `production`
- **Deployment branches**: `main`
- **Protection rules**:
  - ✅ Required reviewers (agregar tu usuario)
  - Timeout: 30 minutes

#### 4. Workflow File
El workflow ya está configurado en `.github/workflows/ci-cd.yml`.

**Triggers**:
- Push a branch `main`
- Pull requests a `main`

### Uso del Pipeline

#### Deploy Automático a QA
```bash
git add .
git commit -m "feat: nueva funcionalidad"
git push origin main
```

El pipeline automáticamente:
1. ✅ Build de UserAPI
2. ✅ Build de Frontend QA y Production
3. ✅ Deploy a QA
4. ✅ Health checks en QA
5. ⏸️ Espera aprobación manual para PROD

#### Aprobar Deploy a Production
1. Ir a **GitHub → Actions → Workflow en ejecución**
2. Verás "Waiting for approval" en el job de producción
3. Click en **Review deployments**
4. Seleccionar `production` y aprobar
5. El deploy a producción continúa automáticamente

#### Monitorear Pipeline
- **GitHub Actions**: Ver logs en tiempo real
- **Cloud Run Logs**:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision" --limit 50
  ```

---

## 🌍 Ambientes

### QA (Quality Assurance)
**Propósito**: Testing pre-producción, validación de features

**Acceso**:
- Frontend: https://frontend-qa-737714447258.us-central1.run.app
- Backend: https://userapi-qa-737714447258.us-central1.run.app

**Características**:
- Deploy automático en cada push a `main`
- Usa imagen Docker con `environment.qa.ts`
- Conecta a mismo DB que producción (shared)

**Cuándo usar**:
- Testing de nuevas features
- Validación de bugs fixes
- Demos a stakeholders antes de liberar a producción

### Production
**Propósito**: Ambiente de producción para usuarios finales

**Acceso**:
- Frontend: https://frontend-737714447258.us-central1.run.app
- Backend: https://userapi-737714447258.us-central1.run.app

**Características**:
- Requiere aprobación manual para deploy
- Usa imagen Docker con `environment.prod.ts`
- Health checks obligatorios post-deployment

**Cuándo usar**:
- Usuarios finales
- Datos reales
- Solo después de validación en QA

---

## 📊 Monitoreo y Logs

### Ver Logs de Cloud Run
```bash
# Logs de UserAPI Production
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=userapi" --limit 100

# Logs de Frontend QA
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=frontend-qa" --limit 100
```

### Cloud Console
- **Cloud Run**: https://console.cloud.google.com/run
- **Cloud SQL**: https://console.cloud.google.com/sql/instances
- **Secret Manager**: https://console.cloud.google.com/security/secret-manager
- **Logs Explorer**: https://console.cloud.google.com/logs

### Health Check Manual
```bash
# Production
curl https://userapi-737714447258.us-central1.run.app/health

# QA
curl https://userapi-qa-737714447258.us-central1.run.app/health
```

**Respuesta esperada**:
```json
{
  "status": "healthy",
  "service": "UserAPI",
  "version": "1.0.0"
}
```

---

## 🧪 Testing

### Backend (UserAPI)
```bash
cd APIs/UserAPI
source venv/bin/activate

# Instalar pytest (si no está)
pip install pytest pytest-asyncio httpx

# Ejecutar tests (cuando se implementen)
pytest
```

### Frontend (Angular)
```bash
cd tf-frontend

# Unit tests con Karma
ng test

# E2E tests con Cypress (si se implementan)
npm run e2e
```

---

## 🔄 Workflow Típico de Desarrollo

### 1. Desarrollar Feature Local
```bash
# Backend
cd APIs/UserAPI
source venv/bin/activate
python main.py

# Frontend (otra terminal)
cd tf-frontend
npm start
```

### 2. Commit y Push
```bash
git checkout -b feature/nueva-funcionalidad
# ... hacer cambios ...
git add .
git commit -m "feat: descripción de la feature"
git push origin feature/nueva-funcionalidad
```

### 3. Crear Pull Request
- Ir a GitHub y crear PR hacia `main`
- El pipeline ejecuta builds automáticamente
- Revisar checks antes de mergear

### 4. Merge a Main
```bash
git checkout main
git pull origin main
# El pipeline automáticamente:
# - Build de todas las imágenes
# - Deploy a QA
# - Espera aprobación para PROD
```

### 5. Validar en QA
- Abrir https://frontend-qa-737714447258.us-central1.run.app
- Probar la nueva funcionalidad
- Si todo funciona bien, aprobar deploy a producción

### 6. Aprobar Deploy a Producción
- Ir a GitHub Actions → Workflow activo
- Click en "Review deployments"
- Aprobar `production`
- Validar en https://frontend-737714447258.us-central1.run.app

---

## 🔧 Troubleshooting

### Pipeline falla en Build
**Error**: `docker build failed`
**Solución**:
- Verificar Dockerfile sintaxis
- Revisar logs en GitHub Actions
- Probar build local: `docker build -t test .`

### Health Check falla en QA/PROD
**Error**: `curl -f ... || exit 1` falla
**Solución**:
- Verificar que el servicio esté corriendo en Cloud Run Console
- Verificar logs: `gcloud logging read ...`
- Revisar que el endpoint `/health` existe
- Intentar curl manual para ver el error específico

### CORS Errors en Frontend
**Error**: `Access to fetch at '...' has been blocked by CORS policy`
**Solución**:
- Verificar que la URL del frontend está en `allow_origins` en `main.py`
- Rebuild y redeploy UserAPI
- Limpiar caché del navegador

### Database Connection Errors
**Error**: `connection to server at ... failed`
**Solución**:
- Verificar que Cloud SQL instance está running
- Verificar DATABASE_URL en Secret Manager
- Verificar formato de conexión (debe usar Unix socket, no IP)
- Revisar permisos del Service Account

### Bcrypt/Passlib Errors
**Error**: `AttributeError: module 'bcrypt' has no attribute '__about__'`
**Solución**:
- Ya resuelto con `bcrypt==4.0.1` en requirements.txt
- Recrear venv si persiste:
  ```bash
  rm -rf venv
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

---

## 📚 Documentación Adicional

- **[decisiones.md](./decisiones.md)**: Decisiones técnicas y arquitectónicas detalladas
- **[CLAUDE.md](./CLAUDE.md)**: Guía del proyecto para Claude Code AI
- **[05-ado-release-pipelines.md](./05-ado-release-pipelines.md)**: Requisitos del TP5

### Recursos Externos
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Angular Documentation](https://angular.dev/)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

---

## 👥 Autores

**Franco Tallone**
- GitHub: [@francotalloneucc](https://github.com/francotalloneucc)
- Email: 2109774@ucc.edu.ar

---

## 📄 Licencia

Este proyecto fue desarrollado como trabajo práctico para la materia **Ingeniería de Software 3** - Universidad Católica de Córdoba (UCC).

---

## 🎓 Información Académica

- **Materia**: Ingeniería de Software 3
- **Trabajo Práctico**: TP5 - Release Pipelines
- **Año**: 2025
- **Universidad**: Universidad Católica de Córdoba (UCC)

---

## 📝 Changelog

### [1.0.0] - 2025-12-07
- ✅ Deployment inicial en GCP
- ✅ CI/CD con GitHub Actions
- ✅ Ambientes QA y Production
- ✅ Health checks implementados
- ✅ Documentación completa (README.md + decisiones.md)
- ✅ Simplificación: Sin CV upload ni email verification

---

**¿Preguntas?** Abrir un issue en GitHub o contactar al autor.

---
*Última actualización: 2025-12-07*
*CI/CD Pipeline: GitHub Actions*
*Deployment: Google Cloud Run*
*Status: En Testing*
