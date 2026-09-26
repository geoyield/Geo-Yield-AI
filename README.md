# GEO-YIELD-AI

**Geo-Yield-AI** es una plataforma SaaS de *Location Intelligence* diseñada para transformar la toma de decisiones en la expansión de cadenas de retail, negocios, franquicias y consultoras inmobiliarias.

Utilizamos un enfoque de **Agente de IA** que combina datos sociodemográficos, análisis geoespacial y validación normativa instantánea mediante arquitectura RAG, accesible tanto por una interfaz web (formulario + mapa) como por un chat en lenguaje natural.

> **Estado del proyecto:** en construcción por fases. Ver [`docs/structure.md`](docs/structure.md) para la estructura vigente del repo y [`docs/adr/`](docs/adr/) para las decisiones de arquitectura tomadas.

### Estado por fases

| Fase | Contenido | Estado |
| :--- | :--- | :--- |
| **0** | Auditoría, limpieza de arquitectura y corrección de infraestructura base | ✅ Cerrada |
| **1** | Capa de datos sociodemográfica y geoespacial (Postgres/PostGIS, ETL, vista `district_scorecard`) | ✅ Cerrada |
| **2** | Motor RAG legal (pgvector, embeddings locales, generación con LLM citando normativa) | ✅ Cerrada |
| **3** | Agente orquestador (combina Fase 1 + Fase 2 en un informe de viabilidad único) | ✅ Cerrada |
| **4** | Frontend Vue + API completa: formulario, mapa con clustering, streaming, visor de normativa, corpus legal ampliado a 10 zonas | ✅ Cerrada |
| **5** | Zona PGM automática por dirección (geocodificación + servicio Identify del AMB) | ✅ Cerrada |
| **6** | Chat conversacional en lenguaje natural | ✅ Cerrada |

<!-- La numeración de fases 4-6 es una propuesta -- ajustar si el equipo ya tiene otra convención acordada. -->

## 📖 Tabla de Contenidos
- [Propuesta de Valor](#-propuesta-de-valor)
- [Características Principales](#-características-principales)
- [Stack Tecnológico](#-stack-tecnológico)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Instalación y Uso](#-instalación-y-uso)
- [Endpoints de la API](#-endpoints-de-la-api)
- [DevOps y Despliegue](#-devops-y-despliegue)
- [Limitaciones conocidas](#-limitaciones-conocidas)
- [Equipo](#-equipo)

---

## 💡 Propuesta de Valor

### El Problema
Abrir un nuevo local comercial conlleva un alto riesgo financiero. Las decisiones suelen basarse en intuiciones o estudios de mercado lentos (semanas) y costosos, que a menudo ignoran las complejas normativas urbanísticas locales (el PGOU o, en el caso de Barcelona, el **PGM — Pla General Metropolità**).

### La Solución
**Geo-Yield-AI** ayuda a evaluar la viabilidad de abrir un bar o restaurante en Barcelona en segundos, no semanas, combinando dos cosas que normalmente se consultan por separado:
* **Datos socioeconómicos por distrito:** renta media, afluencia peatonal, densidad de competencia.
* **Normativa legal aplicable:** qué usos permite la zona urbanística exacta (PGM), citando siempre el artículo concreto.

El usuario puede llegar a esto por dos caminos: un formulario con mapa interactivo, o describiendo lo que quiere hacer en una frase ("quiero abrir un bar en tal calle, ¿me lo recomiendas?").

---

## ✨ Características Principales

1. **Motor RAG Legal:** Ingesta de normativa urbanística (PGM de Barcelona, portal NUMAMB del AMB) partida por artículo, con embeddings locales (**sentence-transformers**) indexados en **pgvector**, y generación de respuestas citando el artículo exacto vía LLM (**Gemini** — ver [`backend/rag/`](backend/rag/)). El corpus cubre 10 zonas urbanísticas del PGM, cada una verificada artículo por artículo contra la fuente original.
2. **Perfilado Sociodemográfico:** Filtros por niveles de renta, afluencia y densidad de competencia, agregados por distrito.
3. **Agente de Viabilidad:** Orquestador con **LangGraph** (`backend/ia/agent.py`) que combina en paralelo los datos socioeconómicos del distrito y la normativa legal de la zona PGM elegida, sintetizando ambos en un informe con semáforo (verde/ámbar/rojo) y citas normativas, transmitido en tiempo real (streaming) palabra por palabra.
4. **Mapa interactivo:** Distrito con competidores reales agrupados (clustering), o radio de 500m alrededor de una dirección exacta cuando se conoce.
5. **Visor de normativa:** Cada cita de artículo en el informe se puede abrir para ver el texto legal completo.
6. **Zona PGM automática:** Dada una dirección, se geocodifica (Nominatim) y se consulta el servicio geoespacial del AMB para determinar la zona urbanística real del punto, sin que el usuario tenga que conocer el código de zonificación. Si no se puede determinar con confianza, se pide que se seleccione manualmente -- nunca se adivina.
7. **Chat conversacional:** El usuario puede describir lo que quiere en una frase libre ("quiero abrir un bar en X, ¿puedo poner terraza?"); el sistema extrae la dirección (o el distrito, si no da una calle exacta) y cualquier pregunta específica, y genera el informe reutilizando el mismo pipeline. Si el usuario pregunta algo que la normativa cargada no cubre, el sistema lo dice explícitamente en vez de inventar una respuesta.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
| :--- | :--- |
| **Lenguaje** | Python 3.12 |
| **IA / RAG** | sentence-transformers (embeddings locales, coste cero) + pgvector + Gemini 2.5 Flash (generación) — ver [`backend/rag/gemini_adapter.py`](backend/rag/gemini_adapter.py) |
| **Agente** | LangGraph (`backend/ia/agent.py`) — orquesta datos + normativa en paralelo, síntesis final en streaming |
| **Geocodificación** | Nominatim (OpenStreetMap) para dirección → coordenadas + distrito; servicio Identify del AMB (`geoportal.amb.cat`) para coordenadas → zona PGM — ver [`backend/geo/`](backend/geo/) |
| **Backend** | FastAPI, servido con Uvicorn |
| **Frontend** | Vue 3 + Vite + Tailwind CSS, mapas con Leaflet y clustering de marcadores |
| **Base de Datos** | PostgreSQL + PostGIS + pgvector, en un único contenedor (`deployment/Dockerfile.postgis`) — ver [ADR 0001](docs/adr/0001-pgvector-vs-qdrant.md) |
| **Data Science** | Pandas |
| **DevOps** | Docker, GitHub Actions, CI/CD, Alembic (migraciones) |

---

## 🏗️ Arquitectura del Sistema

El flujo de datos sigue una estructura **Cloud-Native**:
1. **Ingesta:** Carga de datasets MITMA, del INE, del censo comercial de Barcelona (Open Data BCN) y PDF normativos del PGM (portal NUMAMB), más la API abierta del AMB (`opendata.amb.cat`) para artículos adicionales de zonificación.
2. **Procesamiento:** Limpieza y agregación con Pandas (Fase 1); chunking por artículo y generación de embeddings locales (Fase 2).
3. **Almacenamiento:** Postgres/PostGIS para datos geoespaciales y sociodemográficos, pgvector para los embeddings legales — todo en la misma base de datos.
4. **Consulta:** `backend/rag/query_engine.py` recupera los artículos más relevantes por similitud semántica (combinando normativa de zona + normativa general) y genera una respuesta citando el artículo y la norma exactos.
5. **Síntesis:** `backend/ia/agent.py` (LangGraph) combina en paralelo los datos del distrito y la normativa de la zona PGM elegida en un único informe de viabilidad con semáforo, en modo síncrono o streaming.
6. **Geocodificación:** `backend/geo/geocoding.py` (dirección → distrito) y `backend/geo/amb_identify.py` (coordenadas → zona PGM) resuelven automáticamente lo que antes había que seleccionar a mano, con reintento ante fallos transitorios de los servicios externos.
7. **Chat:** `backend/ia/chat_intent.py` traduce una frase libre a los mismos parámetros estructurados (dirección, distrito, pregunta específica) que el resto del sistema ya sabe manejar -- no es un agente con herramientas, es una capa de extracción de intención de una sola llamada.
8. **API:** FastAPI expone todo lo anterior (ver [Endpoints de la API](#-endpoints-de-la-api)).
9. **Frontend:** Vue consume la API, muestra el informe en tiempo real, el mapa interactivo, y el visor de normativa.

Ver [`docs/diagram.md`](docs/diagram.md) para el diagrama de alto nivel y [`docs/structure.md`](docs/structure.md) para la estructura de carpetas al detalle.

---

## 🚀 Instalación y Uso

### Requisitos previos
* Docker y Docker Compose instalados
* Python 3.12
* Node.js (para el frontend) y `npm`
* `poppler-utils` instalado en el sistema (paquete del SO, no de Python) — necesario para `pdftotext`, usado en la ingesta del corpus legal (Fase 2). En Ubuntu/Debian: `sudo apt install poppler-utils`
* Una API key de **Gemini** (para la generación de respuestas del motor RAG, la síntesis del agente, y la extracción de intención del chat; consíguela en aistudio.google.com/app/apikey) — ver [`backend/rag/gemini_adapter.py`](backend/rag/gemini_adapter.py)

### Pasos para ejecución local con Docker (recomendado, para la base de datos)

1. **Clonar el repositorio:**
```bash
   git clone https://github.com/TU_USUARIO/pj-geo-yield-ai.git
   cd pj-geo-yield-ai
```

2. **Configurar el entorno:**
```bash
   cp .env.example .env
   # Edita .env con tus credenciales (POSTGRES_*, GEMINI_API_KEY)
```

3. **Levantar la base de datos:**
```bash
   docker compose -f deployment/docker-compose.yml up -d --build
```
   La base de datos se construye desde [`deployment/Dockerfile.postgis`](deployment/Dockerfile.postgis) (Postgres 18 + PostGIS + pgvector, ambos vía el repositorio oficial PGDG) — la imagen oficial de `postgis/postgis` por sí sola **no** trae pgvector.

4. **Aplicar las migraciones de base de datos** (desde la raíz del repo, con la BD ya levantada):
```bash
   pip install -r backend/requirements.txt
   DB_HOST_OVERRIDE=localhost alembic -c database/alembic.ini upgrade head
```
   `DB_HOST_OVERRIDE=localhost` sobrescribe el host de `DATABASE_URL` (que
   por defecto apunta a `postgis`, el nombre del servicio dentro de la red
   de Docker, no resoluble desde el host) para poder conectar desde fuera
   del contenedor.

5. **Cargar los datos sociodemográficos** (requiere los CSV de origen en `data/raw/`, ver `backend/etl/config.py` para los nombres esperados):
```bash
   DB_HOST_OVERRIDE=localhost python -m database.load_to_db
```

6. **Cargar el corpus legal** (requiere los PDF de artículos normativos descargados del portal NUMAMB del AMB en un directorio, p. ej. `data/raw/legal/`):
```bash
   DB_HOST_OVERRIDE=localhost python -m database.load_legal_corpus data/raw/legal/
```
   La primera vez descarga el modelo de embeddings (`sentence-transformers/all-MiniLM-L6-v2`, ~90MB) desde Hugging Face — necesitas conexión a internet para ese paso puntual; luego corre en local sin red (puedes fijar `HF_HUB_OFFLINE=1` para evitar comprobaciones de red innecesarias una vez descargado).

   Para ampliar el corpus con las zonas investigadas más allá de las 3 originales, ver [`scripts/pgm_research/`](scripts/pgm_research/) (incluye el proceso completo y `load_new_articles.py`, listo para volver a correr si la base de datos se reinicia).

### Levantar la API (backend)

```bash
DB_HOST_OVERRIDE=localhost uvicorn backend.api.api:app --reload --port 8000
```

Comprueba que responde en `http://localhost:8000/health` y `http://localhost:8000/ready`. La documentación interactiva de todos los endpoints está en `http://localhost:8000/docs` (generada automáticamente por FastAPI).

### Levantar el frontend

```bash
cd frontend
npm install
npm run dev
```

Por defecto arranca en `http://localhost:5173` y espera la API en `http://localhost:8000`. Si la API corre en otra dirección, crea un `frontend/.env` con:

VITE_API_BASE_URL=http://localhost:8000


Con ambos corriendo, abre `http://localhost:5173` en el navegador: ahí están el chat, el formulario, el mapa y el visor de normativa, todo integrado.

### Uso directo del motor RAG y el agente (sin la API, para depuración o notebooks)

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.db.connection import resolve_database_url
from backend.rag.query_engine import generate_answer
from backend.ia.agent import generar_informe_viabilidad, zonas_pgm_disponibles

engine = create_engine(resolve_database_url())
with Session(engine) as session:
    result = generate_answer(session, "¿Puedo abrir un bar en una zona industrial?")
    print(result["respuesta"])

    print(zonas_pgm_disponibles(session))  # zonas con normativa cargada
    informe = generar_informe_viabilidad(session, codi_districte=1, zona_pgm="nucli_antic")
    print(informe["semaforo"], informe["resumen"])
```
Gemini es el proveedor por defecto (no hace falta pasar `llm_client` explícitamente).
<!-- "Cuota gratuita limitada a 20 peticiones/día" -- verificar si sigue siendo así antes de reafirmarlo aquí; el uso real de esta sesión de desarrollo ha sido considerablemente mayor. -->

La zona PGM se puede pedir explícita, o dejar que se determine automáticamente a partir de una dirección (ver `backend/geo/geocoding.py` y `backend/geo/amb_identify.py`) -- un distrito puede abarcar varias zonas PGM distintas, así que sin una dirección exacta no hay forma honesta de saber cuál aplica.

### Ejecutar los tests

```bash
DB_HOST_OVERRIDE=localhost pytest tests/ -v
```

Los tests que necesitan una base de datos real (recuperación por similitud, carga del corpus legal) se saltan automáticamente (no fallan) si no hay una BD accesible — ver [`tests/conftest.py`](tests/conftest.py). Los tests de servicios externos (geocodificación, AMB) usan mocks, no red real.

---

## 🔌 Endpoints de la API

| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/districts` | Lista los 10 distritos de Barcelona |
| `GET` | `/api/pgm-zones` | Lista las zonas PGM con normativa cargada (dinámico, según lo que haya en la base de datos) |
| `POST` | `/api/reports` | Genera un informe completo, de una vez |
| `POST` | `/api/reports/stream` | Igual, pero transmitido en tiempo real (Server-Sent Events) |
| `GET` | `/api/competitors` | Competidores por distrito, o por radio si se indican `lat`/`lon` |
| `GET` | `/api/articles` | Texto completo de un artículo legal (fuente + número) |
| `GET` | `/api/geocode` | Dirección → distrito + zona PGM sugeridos |
| `POST` | `/api/chat/informe/stream` | Frase libre → informe, vía streaming 

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

fields @timestamp, service, level, message, duration_ms
| filter trace_id = "8f3c1a2b4d5e6f70"
| sort @timestamp asc


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

## ⚠️ Limitaciones conocidas

- La geocodificación y la determinación de zona PGM dependen de servicios externos (Nominatim, geoportal del AMB) que pueden fallar o tardar -- el sistema reintenta automáticamente, pero nunca inventa un resultado si no puede confirmarlo.
- El corpus legal cubre 10 de las más de 50 zonas urbanísticas reales del PGM; para el resto, el sistema pide selección manual en vez de adivinar.
- Los datos de afluencia peatonal y renta son promedios por distrito completo, no desagregados por zona ni por franja horaria.
- El chat no incluye un recomendador de distrito: si el usuario no menciona ninguna zona de Barcelona, se le pide que indique al menos un distrito o dirección.

## 👥 Equipo
Proyecto desarrollado por 4 compañeros del Máster en IA, Cloud y DevOps (Pontia):
- Manuel Yerbes García
- Marvin Bernal
- Enmanuel De Oleo
- Claudi Berenguer Sabaté