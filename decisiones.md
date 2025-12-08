# Decisiones Técnicas - TP5 Final Ingeniería de Software 3

## Índice
1. [Arquitectura General](#arquitectura-general)
2. [Simplificaciones para Entorno Académico](#simplificaciones-para-entorno-académico)
3. [Plataforma Cloud](#plataforma-cloud)
4. [Pipeline CI/CD](#pipeline-cicd)
5. [Ambientes](#ambientes)
6. [Base de Datos](#base-de-datos)
7. [Seguridad](#seguridad)
8. [Monitoreo](#monitoreo)

---

## Arquitectura General

### Decisión: Arquitectura de Microservicios Simplificada
**Contexto**: El proyecto original contiene 5 microservicios (UserAPI, CvAnalyzerAPI, JobsAPI, MatcheoAPI, AssistantAPI) y un frontend Angular.

**Decisión**: Para el TP5, se decidió desplegar únicamente **UserAPI + Frontend** por las siguientes razones:
- Fines académicos: Demostrar el pipeline CI/CD completo sin complejidad innecesaria
- Reducción de costos en Google Cloud
- UserAPI es el servicio core que contiene toda la lógica de autenticación y gestión de usuarios
- Permite demostrar los conceptos de DevOps sin sobrecarga operativa

**Consecuencias**:
- ✅ Despliegue más rápido y económico
- ✅ Pipeline CI/CD más simple de mantener
- ✅ Enfoque en calidad sobre cantidad
- ⚠️ Funcionalidad reducida (sin análisis de CV, matching, ni asistente de IA)

---

## Simplificaciones para Entorno Académico

### Decisión: Eliminar Verificación de Email
**Contexto**: El sistema original requería verificación de email con código de 6 dígitos enviado por SMTP.

**Decisión**: Eliminar el paso de verificación de email para simplificar el flujo de registro.

**Implementación**:
- Creados métodos `create_candidato_simple()` y `create_empresa_simple()` en `services.py`
- Usuarios creados directamente con `verified=True` y `email_verified=True`
- Eliminadas referencias a `verification_code` y `verification_expires`
- Frontend redirige directamente a login después de registro exitoso

**Justificación**:
- Evita necesidad de configurar servidor SMTP en producción
- Simplifica testing y demostración del TP
- Enfoque en CI/CD, no en funcionalidades de negocio

### Decisión: Eliminar Upload y Análisis de CV
**Contexto**: El sistema original permitía upload de CV en PDF con análisis automático usando Google Gemini 2.0.

**Decisión**: Eliminar completamente el upload y análisis de CV para candidatos.

**Implementación**:
- Removidos campos `cv_file` de formularios y endpoints
- Eliminadas llamadas a `CvAnalyzerAPI`
- Campo `cv_filename` en base de datos se mantiene como `NULL`
- Removida lógica de validación de CV con IA

**Justificación**:
- Reduce dependencias (no se necesita `CvAnalyzerAPI` ni Google Gemini API)
- Simplifica el registro de candidatos
- Reduce costos de almacenamiento y procesamiento
- Permite enfocarse en el pipeline de deployment

---

## Plataforma Cloud

### Decisión: Google Cloud Platform
**Alternativas consideradas**:
- AWS (Amazon Web Services)
- Azure
- Google Cloud Platform ✅

**Razones para elegir GCP**:
1. **Créditos gratuitos**: $300 USD para nuevas cuentas
2. **Cloud Run**: Servicio serverless que escala automáticamente (pay-per-use)
3. **Integración nativa**: Cloud SQL, Secret Manager, Container Registry en un mismo ecosistema
4. **Simplicidad**: Menos configuración que AWS o Azure para casos de uso básicos
5. **Pricing amigable**: Cloud Run solo cobra cuando hay requests activos

**Servicios GCP utilizados**:
- **Cloud Run**: Hosting de contenedores Docker (UserAPI y Frontend)
- **Cloud SQL**: PostgreSQL managed database
- **Secret Manager**: Gestión segura de credenciales y API keys
- **Container Registry (GCR)**: Almacenamiento de imágenes Docker
- **IAM**: Service accounts y permisos

### Decisión: Cloud Run en lugar de Compute Engine o GKE
**Contexto**: GCP ofrece múltiples opciones para hosting:
- Compute Engine (VMs tradicionales)
- Google Kubernetes Engine (GKE)
- Cloud Run ✅

**Razones**:
- **Serverless**: No hay que gestionar servidores ni infraestructura
- **Autoscaling**: Escala automáticamente de 0 a N instancias según demanda
- **Costo**: Solo se paga cuando hay requests (ideal para proyecto académico)
- **Simplicidad**: Deploy directo desde Docker images
- **HTTPS automático**: Certificados SSL/TLS gestionados automáticamente

**Trade-offs**:
- ✅ Menor costo operativo
- ✅ Deploy más rápido
- ⚠️ Menos control sobre infraestructura (no se necesita para este proyecto)
- ⚠️ Cold starts (aceptable para demo académica)

---

## Pipeline CI/CD

### Decisión: GitHub Actions
**Alternativas consideradas**:
- Azure DevOps Pipelines
- GitLab CI/CD
- Jenkins
- GitHub Actions ✅

**Razones**:
1. **Integración nativa**: El código ya está en GitHub
2. **Free tier generoso**: 2000 minutos/mes para cuentas públicas
3. **YAML declarativo**: Fácil de versionar y mantener
4. **Marketplace**: Abundancia de actions pre-construidas
5. **GitHub Environments**: Soporte nativo para ambientes y aprobaciones manuales

### Decisión: Estrategia de Build
**Decisión**: Build separado para QA y Production con imágenes Docker específicas.

**Implementación**:
```yaml
build-frontend-qa:    # Imagen con environment.qa.ts
build-frontend-prod:  # Imagen con environment.prod.ts
```

**Razones**:
- Diferentes URLs de API backend según ambiente
- Inmutabilidad: La imagen QA no es la misma que PROD
- Trazabilidad: Cada imagen tiene configuración explícita

**Alternativas descartadas**:
- ❌ Variables de entorno en runtime: Angular necesita URLs en build time
- ❌ Única imagen para ambos ambientes: No permite diferentes configuraciones

### Decisión: Estrategia de Tags
**Tags aplicados a cada imagen**:
- `{github.sha}`: Commit hash específico (inmutable)
- `latest`: Última versión buildada

**Razones**:
- `{github.sha}` permite rollback exacto a cualquier versión
- `latest` facilita testing manual rápido
- Cada deploy de Cloud Run referencia el SHA específico

### Decisión: Orden de Deployment
**Flujo**:
```
Build UserAPI → Build Frontend QA → Build Frontend PROD
     ↓                ↓                    ↓
Deploy QA UserAPI → Deploy QA Frontend
     ↓ (Aprobación Manual)
Deploy PROD UserAPI → Deploy PROD Frontend
```

**Razones**:
- Backend antes que frontend (evita errores 503)
- QA siempre antes que PROD
- Aprobación manual entre ambientes (requisito TP5)

---

## Ambientes

### Decisión: Dos Ambientes (QA + Production)
**Ambientes configurados**:

| Ambiente | UserAPI | Frontend | Base de Datos | Propósito |
|----------|---------|----------|---------------|-----------|
| **QA** | `userapi-qa` | `frontend-qa` | Shared DB | Testing pre-producción |
| **Production** | `userapi` | `frontend` | Shared DB | Usuarios finales |

**Decisión importante**: **Base de datos compartida entre QA y PROD**

**Razones**:
- Simplificación para entorno académico
- Reducción de costos (Cloud SQL cobra por instancia)
- Datos de testing no interfieren con producción (volumen bajo)

**Alternativa ideal para producción real**:
- ✅ Bases de datos separadas por ambiente
- ✅ Datos de QA aislados de producción
- ⚠️ Mayor costo y complejidad operativa

### Decisión: GitHub Environments con Manual Approval
**Configuración**:
```yaml
environment:
  name: qa              # Sin aprobaciones

environment:
  name: production     # Requiere aprobación manual
```

**Razones**:
- Cumple con requisito TP5 de aprobaciones manuales
- Previene deployments accidentales a producción
- Permite validar QA antes de liberar a PROD

**Implementación**:
En GitHub: Settings → Environments → production → Required reviewers

---

## Base de Datos

### Decisión: Cloud SQL PostgreSQL
**Alternativas consideradas**:
- Cloud SQL MySQL
- Cloud Firestore (NoSQL)
- Cloud Spanner
- PostgreSQL en Cloud SQL ✅

**Razones**:
1. **Compatibilidad**: El proyecto usa PostgreSQL con SQLAlchemy
2. **Managed service**: Backups automáticos, updates, alta disponibilidad
3. **Cloud SQL Proxy**: Conexión segura sin necesidad de IP públicas
4. **Costo**: Más económico que Spanner para este volumen de datos

### Decisión: Unix Socket Connection (Cloud SQL Proxy)
**Implementación**:
```python
DATABASE_URL=postgresql://postgres:PASSWORD@/userapi?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
```

**Razones**:
- ✅ Más seguro que conexión por IP pública
- ✅ No requiere configurar VPC o whitelisting de IPs
- ✅ Cloud Run tiene soporte nativo para Cloud SQL Proxy
- ✅ Encriptación automática de conexiones

**Alternativa descartada**:
- ❌ IP pública: Requiere whitelist de IPs, menos seguro, más complejo

### Decisión: Configuración de Instancia
**Specs seleccionadas**:
- **Tier**: `db-f1-micro` (1 vCPU compartido, 614 MB RAM)
- **Storage**: 10 GB SSD
- **Región**: `us-central1` (misma que Cloud Run)

**Razones**:
- Suficiente para proyecto académico y demos
- Costo mínimo (~$10/mes)
- Misma región que Cloud Run = menor latencia

---

## Seguridad

### Decisión: Secret Manager para Credenciales
**Secrets almacenados**:
- `DATABASE_URL`: Connection string de PostgreSQL
- `SECRET_KEY`: JWT secret key
- `EMAIL_USER` y `EMAIL_PASSWORD`: Credenciales SMTP (aunque no se usan actualmente)
- `INTERNAL_SERVICE_API_KEY`: Para comunicación entre servicios

**Razones**:
- ✅ Credenciales nunca en código fuente o variables de entorno visibles
- ✅ Versionado de secrets (rollback disponible)
- ✅ Auditoría de accesos
- ✅ Integración nativa con Cloud Run

**Alternativa descartada**:
- ❌ Variables de entorno en Cloud Run: Menos seguro, no versionado

### Decisión: Service Account con Mínimos Privilegios
**Permisos otorgados a `userapi-service-account`**:
- Cloud SQL Client
- Secret Manager Secret Accessor

**Razones**:
- Principio de **least privilege**
- Si el servicio se ve comprometido, daño limitado
- Auditoría clara de qué servicios acceden a qué recursos

### Decisión: CORS Configurado Explícitamente
**Orígenes permitidos**:
```python
allow_origins=[
    "http://localhost:4200",        # Desarrollo
    "https://frontend-qa-...",      # QA
    "https://frontend-..."          # Production
]
```

**Razones**:
- ✅ Solo frontends legítimos pueden hacer requests
- ✅ Previene ataques CSRF desde dominios maliciosos
- ❌ Evita wildcard `"*"` que sería inseguro

### Decisión: Bcrypt para Hashing de Passwords
**Configuración**:
```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

**Implementación crítica**:
- **Truncado a 72 bytes**: Bcrypt tiene límite de 72 bytes
- **Implementado en 3 niveles**: endpoint, service, auth module

**Razones**:
- ✅ bcrypt es estándar de industria para password hashing
- ✅ Resistente a ataques de fuerza bruta (computacionalmente costoso)
- ✅ Integración sencilla con Passlib

**Problema resuelto**:
- Error inicial: `AttributeError: module 'bcrypt' has no attribute '__about__'`
- Solución: Pinear `bcrypt==4.0.1` (compatible con `passlib==1.7.4`)

---

## Monitoreo

### Decisión: Health Checks en Pipeline
**Implementación**:
```yaml
- name: Health Check QA UserAPI
  run: |
    sleep 10
    curl -f ${{ steps.qa-url.outputs.url }}/health || exit 1
```

**Endpoints de health check**:
- `/health`: Endpoint raíz (también definido en routes.py)
- Respuesta:
```json
{
  "status": "healthy",
  "service": "UserAPI",
  "version": "1.0.0"
}
```

**Razones**:
- ✅ Pipeline falla si deployment no responde correctamente
- ✅ Detecta problemas de configuración inmediatamente
- ✅ Previene deployments rotos llegando a producción

### Decisión: Cloud Run Logging
**Por defecto habilitado**:
- Logs de requests HTTP
- Logs de aplicación (stdout/stderr)
- Métricas de latencia, requests/s, errores

**Razones**:
- ✅ Sin configuración adicional necesaria
- ✅ Integrado con Cloud Logging (Stackdriver)
- ✅ Búsqueda y filtrado avanzado
- ✅ Retention configurable

**No implementado (por ahora)**:
- ⚠️ Alertas automáticas (no crítico para TP académico)
- ⚠️ Dashboards personalizados
- ⚠️ APM (Application Performance Monitoring)

---

## Gestión de Código

### Decisión: Monorepo
**Estructura**:
```
/
├── APIs/
│   └── UserAPI/
├── tf-frontend/
└── .github/workflows/
```

**Razones**:
- ✅ Único repositorio para backend + frontend
- ✅ Cambios atómicos (un commit puede actualizar ambos)
- ✅ Pipeline único maneja todo el deployment
- ❌ Evita complejidad de múltiples repos para proyecto académico

**Alternativa descartada**:
- ❌ Repos separados: Mayor complejidad de coordinación

### Decisión: Dockerfiles Multi-stage
**Frontend**:
```dockerfile
FROM node:20-alpine AS build     # Build de Angular
FROM nginx:alpine                # Serve estático
```

**Backend**:
```dockerfile
FROM python:3.11-slim
# Single stage (no se necesita compilación)
```

**Razones**:
- ✅ Imágenes más livianas (solo runtime en imagen final)
- ✅ Build más rápido en pipeline
- ✅ Mejor para producción

---

## Costos

### Estimación Mensual (USD)
| Servicio | Configuración | Costo Estimado |
|----------|---------------|----------------|
| Cloud Run (UserAPI QA) | Pay-per-use | ~$1-3 |
| Cloud Run (UserAPI PROD) | Pay-per-use | ~$2-5 |
| Cloud Run (Frontend QA) | Pay-per-use | ~$0.50 |
| Cloud Run (Frontend PROD) | Pay-per-use | ~$0.50 |
| Cloud SQL PostgreSQL | db-f1-micro | ~$10 |
| Container Registry | Storage | ~$0.50 |
| Secret Manager | Secrets + accesos | ~$0.20 |
| **TOTAL** | | **~$15-20/mes** |

**Nota**: Con créditos de $300, el proyecto puede correr ~15-20 meses sin costo.

---

## Decisiones Pendientes / Mejoras Futuras

### Si esto fuera producción real:
1. **Bases de datos separadas** para QA y PROD
2. **CDN** (Cloud CDN) para el frontend
3. **Load balancing** con Cloud Load Balancer
4. **Autoscaling avanzado** con mínimo de instancias warm
5. **Monitoring y alerting** con Cloud Monitoring
6. **WAF** (Web Application Firewall) con Cloud Armor
7. **Disaster recovery** con backups automatizados y cross-region
8. **CI con tests automatizados** (unit, integration, e2e)
9. **Feature flags** para deployments graduales
10. **Rollback automatizado** si health checks fallan

---

## Resumen de Decisiones Clave

| Decisión | Elección | Justificación |
|----------|----------|---------------|
| **Cloud Provider** | Google Cloud Platform | Créditos gratuitos, simplicidad, Cloud Run |
| **Hosting** | Cloud Run | Serverless, autoscaling, pay-per-use |
| **Base de Datos** | Cloud SQL PostgreSQL | Managed, compatible con proyecto existente |
| **CI/CD** | GitHub Actions | Integración nativa, free tier, YAML |
| **Ambientes** | QA + Production | Requisito TP5, aprobaciones manuales |
| **Seguridad** | Secret Manager + Service Accounts | Best practices de GCP |
| **Simplificaciones** | Sin CV ni email verification | Enfoque académico en DevOps |
| **Monorepo** | Backend + Frontend juntos | Simplicidad para TP |

---

**Fecha**: Diciembre 2025
**Materia**: Ingeniería de Software 3
**Trabajo Práctico**: TP5 - Release Pipelines
