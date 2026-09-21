# GEO-YIELD-AI

**Geo-Yield-AI** es una plataforma SaaS de *Location Intelligence* diseñada para transformar la toma de decisiones en la expansión de cadenas de retail, negocios, franquicias y consultoras inmobiliarias.

Utilizamos un enfoque de **Agente de IA Autónomo** que combina Big Data de movilidad, análisis sociodemográfico y validación normativa instantánea mediante arquitectura RAG.

> **Estado del proyecto:** en construcción por fases. Ver [`docs/structure.md`](docs/structure.md) para la estructura vigente del repo y [`docs/adr/`](docs/adr/) para las decisiones de arquitectura tomadas.

### Estado por fases

| Fase | Contenido | Estado |
| :--- | :--- | :--- |
| **0** | Auditoría, limpieza de arquitectura y corrección de infraestructura base | ✅ Cerrada |
| **1** | Capa de datos sociodemográfica y geoespacial (Postgres/PostGIS, ETL, vista `district_scorecard`) | ✅ Cerrada |
| **2** | Motor RAG legal (pgvector, embeddings locales, generación con LLM citando normativa) | ✅ Cerrada |
| **3** | Agente orquestador (combina Fase 1 + Fase 2 en un informe de viabilidad único) | ✅ Cerrada |

## 📖 Tabla de Contenidos
- [Propuesta de Valor](#-propuesta-de-valor)
- [Características Principales](#-características-principales)
- [Stack Tecnológico](#-stack-tecnológico)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Instalación y Uso](#-instalación-y-uso)
- [DevOps y Despliegue](#-devops-y-despliegue)
- [Equipo](#-equipo)

---

## 💡 Propuesta de Valor

### El Problema
Abrir un nuevo local comercial conlleva un alto riesgo financiero. Las decisiones suelen basarse en intuiciones o estudios de mercado lentos (semanas) y costosos, que a menudo ignoran las complejas normativas urbanísticas locales (el PGOU o, en el caso de Barcelona, el **PGM — Pla General Metropolità**).

### La Solución
**Geo-Yield-AI** actúa como un consultor inmobiliario 360° que reduce el tiempo de evaluación de semanas a segundos:
* **Validación Hiper-Local:** Mapas de calor de afluencia peatonal real.
* **Inteligencia Legal:** Interpretación automática de leyes urbanas para confirmar la viabilidad de licencias.
* **Análisis de Mercado:** Perfilado demográfico y mapeo de la competencia.

---

## ✨ Características Principales

1. **Análisis de Movilidad Dinámica:** Procesamiento de Big Data del **MITMA** (Ministerio de Transportes) para identificar flujos de personas por distrito.
2. **Motor RAG Legal:** Ingesta de normativa urbanística (PGM de Barcelona, portal NUMAMB del AMB) partida por artículo, con embeddings locales (**sentence-transformers**) indexados en **pgvector**, y generación de respuestas citando el artículo exacto vía LLM (**Gemini** — ver [`backend/rag/`](backend/rag/)).
3. **Perfilado Sociodemográfico:** Filtros por niveles de renta, afluencia y densidad de competencia, agregados por distrito.
4. **Agente de Viabilidad:** Orquestador con **LangGraph** (`backend/ia/agent.py`) que combina en paralelo los datos socioeconómicos del distrito (Fase 1) y la normativa legal de la zona PGM elegida (Fase 2), sintetizando ambos en un informe con semáforo (verde/ámbar/rojo) y citas normativas — el usuario elige la zona urbanística explícitamente, ya que un distrito puede abarcar varias zonas PGM distintas.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
| :--- | :--- |
| **Lenguaje** | Python 3.12 |
| **IA / RAG** | sentence-transformers (embeddings locales, coste cero) + pgvector + Gemini 2.5 Flash (generación) — ver [`backend/rag/gemini_adapter.py`](backend/rag/gemini_adapter.py) |
| **Agente** | LangGraph (`backend/ia/agent.py`) — orquesta Fase 1 + Fase 2 en paralelo, síntesis final con LLM |
| **Backend** | FastAPI |
| **Frontend** | Vue 3 + Vite + Tailwind (mapas interactivos con Leaflet) |
| **Base de Datos** | PostgreSQL + PostGIS + pgvector, en un único contenedor (`deployment/Dockerfile.postgis`) — ver [ADR 0001](docs/adr/0001-pgvector-vs-qdrant.md) |
| **Data Science** | Pandas |
| **DevOps** | Docker, GitHub Actions, CI/CD, Alembic (migraciones) |

---

## 🏗️ Arquitectura del Sistema

El flujo de datos sigue una estructura **Cloud-Native**:
1. **Ingesta:** Carga de datasets MITMA, del INE, del censo comercial de Barcelona (Open Data BCN) y PDF normativos del PGM (portal NUMAMB).
2. **Procesamiento:** Limpieza y agregación con Pandas (Fase 1); chunking por artículo y generación de embeddings locales (Fase 2).
3. **Almacenamiento:** Postgres/PostGIS para datos geoespaciales y sociodemográficos, pgvector para los embeddings legales — todo en la misma base de datos.
4. **Consulta:** `backend/rag/query_engine.py` recupera los artículos más relevantes por similitud semántica y genera una respuesta citando el artículo correspondiente.
5. **Síntesis:** `backend/ia/agent.py` (LangGraph) combina en paralelo los datos del distrito (paso 3, Fase 1) y la normativa de la zona PGM elegida (paso 4, Fase 2) en un único informe de viabilidad con semáforo.

> Nota: el agente hoy se invoca directamente como módulo Python (ver ejemplos de uso más abajo); exponerlo como endpoint de la API es el siguiente paso natural, no construido todavía.

Ver [`docs/diagram.md`](docs/diagram.md) para el diagrama de alto nivel y [`docs/structure.md`](docs/structure.md) para la estructura de carpetas al detalle.

---

## 🚀 Instalación y Uso

### Requisitos previos
* Docker y Docker Compose instalados
* Python 3.12
* `poppler-utils` instalado en el sistema (paquete del SO, no de Python) — necesario para `pdftotext`, usado en la ingesta del corpus legal (Fase 2). En Ubuntu/Debian: `sudo apt install poppler-utils`
* Una API key de **Gemini** (para la generación de respuestas del motor RAG; consíguela en aistudio.google.com/app/apikey) — ver [`backend/rag/gemini_adapter.py`](backend/rag/gemini_adapter.py)

### Pasos para ejecución local con Docker (recomendado)

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/TU_USUARIO/pj-geo-yield-ai.git
   cd pj-geo-yield-ai
   ```

2. **Configurar el entorno:**
   ```bash
   cp .env.example .env
   # Edita .env con tus credenciales (POSTGRES_*, GEMINI_API_KEY, y opcionalmente ANTHROPIC_API_KEY si se retoma en el futuro)
   ```

3. **Levantar la API y la base de datos:**
   ```bash
   docker compose -f deployment/docker-compose.yml up -d --build
   ```
   La base de datos se construye desde [`deployment/Dockerfile.postgis`](deployment/Dockerfile.postgis) (Postgres 18 + PostGIS + pgvector, ambos vía el repositorio oficial PGDG) — la imagen oficial de `postgis/postgis` por sí sola **no** trae pgvector. La API queda disponible en `http://localhost:8080`. Comprueba `GET /health` y `GET /ready`.

4. **Aplicar las migraciones de base de datos** (desde la raíz del repo, con la BD ya levantada):
   ```bash
   pip install -r backend/requirements.txt
   DB_HOST_OVERRIDE=localhost alembic -c database/alembic.ini upgrade head
   ```
   `DB_HOST_OVERRIDE=localhost` sobrescribe el host de `DATABASE_URL` (que
   por defecto apunta a `postgis`, el nombre del servicio dentro de la red
   de Docker, no resoluble desde el host) para poder conectar desde fuera
   del contenedor. El puerto de Postgres está publicado al host en
   `deployment/docker-compose.yml` precisamente para esto.

5. **Cargar los datos sociodemográficos** (requiere los CSV de origen en `data/raw/`, ver `backend/etl/config.py` para los nombres esperados):
   ```bash
   DB_HOST_OVERRIDE=localhost python -m database.load_to_db
   ```

6. **Cargar el corpus legal** (requiere los PDF de artículos normativos descargados del portal NUMAMB del AMB en un directorio, p. ej. `data/raw/legal/`):
   ```bash
   DB_HOST_OVERRIDE=localhost python -m database.load_legal_corpus data/raw/legal/
   ```
   La primera vez descarga el modelo de embeddings (`sentence-transformers/all-MiniLM-L6-v2`, ~90MB) desde Hugging Face — necesitas conexión a internet para ese paso puntual; luego corre en local sin red (puedes fijar `HF_HUB_OFFLINE=1` para evitar comprobaciones de red innecesarias una vez descargado).

7. **Consultar el motor RAG** (requiere el paso 6 ya hecho, y `GEMINI_API_KEY` en tu `.env`):
   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.orm import Session
   from backend.db.connection import resolve_database_url
   from backend.rag.query_engine import generate_answer

   engine = create_engine(resolve_database_url())
   with Session(engine) as session:
       result = generate_answer(session, "¿Puedo abrir un bar en una zona industrial?")
       print(result["respuesta"])
   ```
   Gemini es el proveedor por defecto (no hace falta pasar `llm_client` explícitamente). Cuota gratuita limitada a 20 peticiones/día — ver [`backend/rag/gemini_adapter.py`](backend/rag/gemini_adapter.py) si en el futuro se quisiera usar otro proveedor.

8. **Generar un informe de viabilidad completo** (Fase 3, requiere los pasos 5-7 ya hechos):
   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.orm import Session
   from backend.db.connection import resolve_database_url
   from backend.ia.agent import generar_informe_viabilidad, zonas_pgm_disponibles

   engine = create_engine(resolve_database_url())
   with Session(engine) as session:
       print(zonas_pgm_disponibles(session))  # zonas con normativa cargada
       informe = generar_informe_viabilidad(session, codi_districte=1, zona_pgm="nucli_antic")
       print(informe["semaforo"], informe["resumen"])
   ```
   La zona PGM se pide explícita a propósito (no se infiere del distrito): un distrito puede abarcar varias zonas PGM distintas, y sin datos geoespaciales reales del planeamiento no hay forma honesta de adivinarla automáticamente.

### Ejecución local sin Docker (solo la API)

1. **Instalar dependencias:**
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Configurar el entorno:**
   ```bash
   cp .env.example .env
   # Cambia el host de DATABASE_URL de "postgis" a "localhost" si la base
   # de datos corre en Docker con el puerto publicado, o apunta a tu propia
   # instancia de Postgres/PostGIS local.
   ```

3. **Ejecutar la aplicación (desde la raíz del repo):**
   ```bash
   python -m backend.api.main
   ```

### Ejecutar los tests

```bash
DB_HOST_OVERRIDE=localhost pytest tests/ -v
```

Los tests que necesitan una base de datos real (recuperación por similitud, carga del corpus legal) se saltan automáticamente (no fallan) si no hay una BD accesible — ver [`tests/conftest.py`](tests/conftest.py).

---

## 🔄 DevOps y Despliegue
Este proyecto aplica los conocimientos de ingeniería adquiridos en el Máster:

- **Contenedores:** Imágenes Docker propias para la API (`deployment/Dockerfile`) y para la base de datos (`deployment/Dockerfile.postgis`, Postgres + PostGIS + pgvector), para que el entorno de desarrollo sea idéntico al de producción.
- **Migraciones:** Alembic, versionadas en `database/alembic/versions/` — cada cambio de esquema es un fichero nuevo, nunca se edita uno ya aplicado.
- **CI/CD:** Pipeline en GitHub Actions (`integrate.yml`) que ejecuta los tests en cada pull request, y despliegue manual (`deploy.yml`) a Render.
- **Observabilidad:** Logging estructurado en JSON compartido por backend y frontend (ver *Structured logging* más abajo), más el contador de peticiones de `/metrics`. Las métricas específicas del agente/RAG (latencia del LLM, tasa de citas verificadas) se añadirán en la Fase 3.

### Structured logging

Backend and frontend emit **the same JSON schema**, so a single CloudWatch Logs Insights query covers both:

```json
{"timestamp":"...","level":"ERROR","service":"geoyield-api","env":"production","version":"0.1.0",
 "logger":"geoyield_api","message":"...","trace_id":"8f3c1a2b4d5e6f70","duration_ms":1234,
 "error":{"type","message","stack"},"context":{"codi_districte":"01"}}
```

| | Where | Usage |
|---|---|---|
| Backend | `backend/observability/` | `logging.getLogger("geoyield_api")` as before; only the formatter changed. For structured context, `log_event(logger, "INFO", "msg", codi_districte="01")`. |
| Frontend | `frontend/src/services/logger.js` | `import { createLogger } from './services/logger.js'` → `log.error('msg', { error })`, `log.event('informe.generado', {...})`. |

**Correlation.** The frontend generates a `trace_id` per call and sends it in the `X-Request-ID` header. The backend propagates it to *all* of its log lines for that request (RAG, agent and database included), so a user click can be traced end to end:

```
fields @timestamp, service, level, message, duration_ms
| filter trace_id = "8f3c1a2b4d5e6f70"
| sort @timestamp asc
```

**Local vs production.** Behaviour is derived from `ENV` (and from the Vite build mode on the frontend), so there is nothing to configure for day-to-day work:

| | Local (`ENV=development`, `npm run dev`) | Production (`ENV=production`, `npm run build`) |
|---|---|---|
| Format | Readable coloured text | One JSON line per event |
| Level | DEBUG | INFO |
| Backend logs | Console / `docker compose logs` | stdout, collected by the host |
| Frontend logs | Browser console only | Browser console + `POST /api/logs` |
| CloudWatch | Never | When `LOG_CLOUDWATCH_GROUP` is set |

`LOG_LEVEL`, `LOG_FORMAT`, `LOG_CLOUDWATCH_ENABLED` and `VITE_LOG_REMOTE` override any of this, for example to reproduce the production format locally:

```bash
LOG_FORMAT=json python -m backend.api.main
docker compose -f deployment/docker-compose.yml logs -f api | jq .
```

**How logs reach CloudWatch.** The browser cannot talk to CloudWatch without exposing AWS credentials, so it posts batches to `POST /api/logs` and the backend re-emits them through its own logger. From there, two routes:

1. **stdout (default, recommended).** On ECS/Fargate/App Runner the host driver (`awslogs`/FireLens) already collects it: no boto3, no credentials, no added latency and no `PutLogEvents` rate limit. Leave `LOG_CLOUDWATCH_GROUP` empty there.
2. **Direct shipping.** For hosts that do *not* collect stdout, such as Render. Set `LOG_CLOUDWATCH_GROUP` and install the optional `boto3` and `watchtower` (commented out in `backend/requirements.txt`). It only activates when `ENV=production`.

**Privacy (GDPR).** The geocoder's free-text address is personal data and is never logged; the resulting district and zone are stored instead. `backend/observability/logging_config.py` also redacts a set of sensitive keys (`direccion`, `email`, `token`, `api_key`...) both in our own logs and in those arriving from the browser.

## 👥 Equipo
Proyecto desarrollado por 4 compañeros del Máster en IA, Cloud y DevOps (Pontia):
- Manuel Yerbes García
- Marvin Bernal
- Enmanuel De Oleo
- Claudi Berenguer Sabaté