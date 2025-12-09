# Pipeline CI/CD - Resumen

Pipeline completo de CI/CD con GitHub Actions que automatiza testing, análisis de calidad, builds y deploys a Google Cloud Run.

**Archivo principal**: `.github/workflows/deploy.yml`

---

## FASE 1: Tests en Paralelo

Ejecuta tests unitarios de backend y frontend simultáneamente para optimizar tiempo de ejecución.

### **test-backend** → Pytest con coverage
- **Herramientas**: pytest, pytest-cov, SQLite (test.db)
- **Tests**: `APIs/UserAPI/tests/test_complete.py`
- **Genera**: `APIs/UserAPI/coverage.xml`
- **Explicación**: Ejecuta todos los tests unitarios del backend UserAPI usando una base de datos SQLite temporal, calculando cobertura de código.

### **test-frontend** → Angular unit tests
- **Herramientas**: Karma, Jasmine, ChromeHeadless
- **Tests**: `tf-frontend/src/**/*.spec.ts`
- **Genera**: `tf-frontend/coverage/tf-frontend/lcov.info`
- **Explicación**: Ejecuta tests unitarios de componentes, servicios y guards del frontend Angular en un navegador headless.

---

## FASE 2: Quality Gate

Análisis de calidad de código usando los reportes de coverage de la fase anterior.

### **sonarcloud** → Análisis estático y coverage
- **Herramientas**: SonarCloud Scanner, SonarQube analysis
- **Config**: `sonar-project.properties` (raíz del proyecto)
- **Workflow**: `.github/workflows/deploy.yml:128-220`
- **Explicación**: Analiza calidad de código (bugs, code smells, vulnerabilidades, duplicaciones), revisa coverage y aplica Quality Gate definido en SonarCloud.

---

## FASE 3: Builds en Paralelo

Construcción de imágenes Docker del backend y frontend (QA) simultáneamente.

### **build-userapi** → Docker image del backend
- **Herramientas**: Docker, Google Cloud Artifact Registry
- **Dockerfile**: `APIs/UserAPI/Dockerfile`
- **Explicación**: Construye imagen Docker del backend con Python 3.12, instala dependencias y sube a Artifact Registry con tag del commit SHA.

### **build-frontend-qa** → Docker image del frontend (QA)
- **Herramientas**: Docker, Angular build (environment QA)
- **Dockerfile**: `tf-frontend/Dockerfile`
- **Explicación**: Construye imagen del frontend con configuración de QA (environment.qa.ts), compila con Angular CLI y sube a Artifact Registry.

---

## FASE 4: Deploy QA

Despliegue automático al ambiente de QA (sin aprobación manual).

### **deploy-qa** → Backend a Cloud Run QA
- **Herramientas**: gcloud CLI, Cloud Run
- **Service**: `userapi-qa`
- **URL**: https://userapi-qa-737714447258.us-central1.run.app
- **Explicación**: Despliega imagen Docker del backend a Cloud Run, inyecta secrets desde Secret Manager y conecta a Cloud SQL.

### **deploy-frontend-qa** → Frontend a Cloud Run QA
- **Herramientas**: gcloud CLI, Cloud Run
- **Service**: `frontend-qa`
- **URL**: https://frontend-qa-737714447258.us-central1.run.app
- **Explicación**: Despliega imagen Docker del frontend a Cloud Run con configuración de QA, expone puerto 8080.

---

## FASE 5: Smoke Tests

Verificación básica de salud de los servicios desplegados en QA.

### **smoke-tests** → Health checks
- **Herramientas**: curl (HTTP requests)
- **Explicación**: Ejecuta requests HTTP simples a los endpoints de backend y frontend en QA para verificar que responden correctamente y el HTML contiene elementos esperados.

---

## FASE 6: E2E Tests

Tests end-to-end contra el ambiente de QA real.

### **cypress-tests** → Tests de integración
- **Herramientas**: Cypress, Chrome browser
- **Tests**: `tf-frontend/cypress/e2e/`
  - `01-landing.cy.ts` - Tests de landing page
  - `02-register-candidato.cy.ts` - Registro de candidatos
  - `03-register-empresa.cy.ts` - Registro de empresas
- **Explicación**: Ejecuta tests automatizados simulando interacciones reales de usuario (click, formularios, navegación) contra la app desplegada en QA.

---

## FASE 7: Deploy Producción (Backend)

Despliegue del backend a producción **con aprobación manual requerida**.

### **deploy-production** → Backend a Cloud Run Prod
- **Herramientas**: gcloud CLI, Cloud Run
- **Service**: `userapi`
- **URL**: https://userapi-737714447258.us-central1.run.app
- **Environment**: `production` ⚠️ Requiere aprobación manual
- **Explicación**: Despliega la misma imagen del backend (ya testeada en QA) a producción, con configuración de producción (tokens JWT con mayor duración).

### **build-frontend-prod** → Build imagen prod (paralelo)
- **Herramientas**: Docker, Angular build (environment production)
- **Dockerfile**: `tf-frontend/Dockerfile`
- **Explicación**: Construye imagen del frontend con configuración de producción (environment.prod.ts), optimizada para producción.

---

## FASE 8: Deploy Frontend Prod

Despliegue del frontend a producción **con aprobación manual requerida**.

### **deploy-frontend-prod** → Frontend a Cloud Run Prod
- **Herramientas**: gcloud CLI, Cloud Run
- **Service**: `frontend`
- **URL**: https://frontend-737714447258.us-central1.run.app
- **Environment**: `production` ⚠️ Requiere aprobación manual
- **Explicación**: Despliega la imagen de frontend a producción, expone puerto 8080 públicamente.

---

## Trigger

El pipeline se ejecuta automáticamente con cada **push a la rama `main`**.

```yaml
on:
  push:
    branches: [main]
```

---

## Duración Estimada

- **Hasta QA**: ~10-17 minutos (automático)
- **Con Producción**: ~12-20 minutos (+ tiempo de aprobación manual)

---

## Secrets Requeridos

### GitHub Secrets:
- `GCP_SA_KEY` - Service Account Key de GCP
- `SONAR_TOKEN` - Token de SonarCloud
- `CODECOV_TOKEN` - Token de Codecov (opcional)
- `CYPRESS_RECORD_KEY` - Cypress Dashboard (opcional)

### GCP Secret Manager (inyectados en Cloud Run):
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT secret key
- `EMAIL_USER` / `EMAIL_PASSWORD` - SMTP credentials
- `INTERNAL_SERVICE_API_KEY` - Inter-service auth

---

## Aprobación Manual de Producción

Para aprobar deploy a producción:
1. Ve a: https://github.com/francotalloneucc/final-ingsw3/actions
2. Selecciona el workflow run
3. Click en **"Review deployments"**
4. Marca **"production"**
5. Click **"Approve and deploy"**

---

**Última actualización**: Diciembre 2025
