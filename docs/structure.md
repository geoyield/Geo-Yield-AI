# Estructura del repositorio

Esta es la estructura vigente del proyecto (Fase 0 en adelante). Sustituye a
`README_repo_desc.md`, que describía una estructura de un ejercicio anterior
del máster (`src/model.py`, `unit_tests/`, `model tests/`) ya no aplicable a
Geo-Yield-AI — ese fichero debe eliminarse del repo.

```
.
├── backend/
│   ├── api/
│   │   ├── main.py          # Punto de entrada (uvicorn), logging, carga de .env
│   │   ├── api.py           # App FastAPI: lifespan, /health, /ready, /metrics
│   │   ├── schemas/         # DTOs Pydantic del dominio (Fase 3-4)
│   │   └── metrics/         # Métricas in-memory básicas
│   ├── db/
│   │   ├── base.py           # Base declarativa de SQLAlchemy
│   │   ├── models.py         # District, Neighborhood, Competitor (geoespacial),
│   │   │                      # DistrictIncome, DistrictMobility
│   │   └── connection.py     # resolve_database_url() -- override de host para
│   │                          # herramientas ejecutadas fuera de Docker (Alembic, loader)
│   ├── etl/
│   │   ├── config.py          # Rutas portables (data/raw, data/processed)
│   │   ├── income.py          # Renta media por distrito (fuente: INE)
│   │   ├── mobility.py        # Afluencia peatonal por distrito (fuente: MITMA)
│   │   └── competitors.py     # Competidores de hostelería + dimensiones geográficas
│   ├── rag/
│   │   ├── chunking.py         # Parser de artículos legales (web y PDF, NUMAMB)
│   │   ├── pdf_extraction.py   # Extracción de texto de PDF (pdftotext)
│   │   ├── embeddings.py       # Embeddings locales (sentence-transformers, coste cero)
│   │   └── query_engine.py     # Recuperación (pgvector) + generación (Claude)
│   ├── ia/
│   │   └── agent.py         # Agente orquestador (Fase 3): LangGraph, combina
│   │                          # Fase 1 (datos) + Fase 2 (RAG legal) en un informe
│   └── requirements.txt
│
├── database/
│   ├── alembic.ini            # Config de Alembic (ejecutar desde la raíz del repo)
│   ├── alembic/
│   │   ├── env.py             # Carga DATABASE_URL desde el .env de la raíz
│   │   └── versions/
│   │       ├── 0001_initial_schema.py       # Tablas + vista district_scorecard
│   │       ├── 0002_widen_competitor_id.py  # id_global VARCHAR(36) -> VARCHAR(64)
│   │       ├── 0003_legal_chunks.py         # Tabla legal_chunks (pgvector, embedding 384-dim)
│   │       └── 0004_zona_pgm.py             # Columna zona_pgm para filtro exacto por zona urbanística
│   ├── load_to_db.py          # Orquestador: ETL sociodemográfico -> Postgres
│   └── load_legal_corpus.py   # Orquestador: PDF normativa -> chunks -> embeddings -> Postgres
│
├── data/                       # Datos crudos y procesados (gitignored)
│   ├── raw/                    # Ficheros de origen (censo, INE, MITMA)
│   └── processed/              # Salidas intermedias de los notebooks
│
├── notebooks/                 # EDA y prototipado de datos (MITMA, INE, GenCAT)
│
├── frontend/                  # Vue 3 + Vite
│
├── deployment/
│   ├── Dockerfile             # Build con contexto en la raíz del repo
│   ├── docker-compose.yml     # api + postgis (Postgres/PostGIS + pgvector)
│   └── .dockerignore
│
├── docs/
│   ├── structure.md            # Este documento
│   ├── data-sources.md         # Fuentes de datos (pendiente de completar)
│   ├── diagram.md              # Diagrama de arquitectura de alto nivel
│   └── adr/                    # Decisiones de arquitectura (Architecture Decision Records)
│
├── tests/
│   ├── conftest.py               # Fixture db_session (se salta con gracia sin BD real)
│   ├── unit_tests/
│   │   ├── test_api.py             # Tests de los endpoints de FastAPI
│   │   ├── test_etl.py             # Tests de las funciones puras de transformación
│   │   ├── test_chunking.py        # Tests del parser de artículos legales
│   │   ├── test_query_engine.py    # Tests del motor de consulta RAG (necesita BD real)
│   │   ├── test_gemini_adapter.py  # Tests del adaptador de Gemini
│   │   └── test_agent.py           # Tests del agente orquestador (necesita BD real)
│   └── model_tests/             # Se reutilizará para tests del agente en fases posteriores
│
├── .github/workflows/
│   ├── integrate.yml            # CI: tests en pull request
│   ├── check-branch-name.yml    # Valida convención de nombres de rama y Git-Flow
│   └── deploy.yml               # CD manual a Render
│
├── .env.example                 # Plantilla única de variables de entorno
└── README.md
```

## Notas

- **Un único `.env`** vive en la raíz del repo. `docker-compose.yml` lo
  referencia como `../.env` en vez de duplicar variables en un `.env`
  aparte dentro de `deployment/`. Alembic (`database/alembic/env.py`) lee
  el mismo fichero.
- El paquete Python raíz es `backend` (`backend/__init__.py`), de modo que
  la app se ejecuta como `python -m backend.api.main` desde la raíz del
  repo, tanto en local como dentro del contenedor Docker.
- `backend/ia/agent.py` es el punto de entrada previsto para el orquestador
  del agente (Fase 3). Hoy está vacío intencionadamente.
- **Jerarquía geográfica** (Fase 1): `District` (10) → `Neighborhood`
  (barrio) → `Competitor` (local individual, con geometría punto real). Los
  10 distritos son una lista de referencia estática en
  `backend/etl/competitors.py` (no se derivan del censo, ver comentario en
  el propio código); los barrios sí se derivan del censo completo.
- **`district_scorecard`** es una VISTA, no una tabla: el `Opportunity_Score`
  se calcula al vuelo a partir de `district_income`, `district_mobility` y
  `competitors`, para que nunca quede desincronizado.
- Migraciones: `DB_HOST_OVERRIDE=localhost alembic -c database/alembic.ini upgrade head`
  (ejecutar siempre desde la raíz del repo; `DB_HOST_OVERRIDE` solo hace
  falta si se ejecuta fuera de Docker, ver `backend/db/connection.py`).
  Carga de datos: `DB_HOST_OVERRIDE=localhost python -m database.load_to_db`
  (requiere los ficheros en `data/raw/`, ver `backend/etl/config.py` para
  los nombres esperados).
