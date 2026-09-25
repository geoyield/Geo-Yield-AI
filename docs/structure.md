# Estructura del Repositorio (Geo-Yield-AI)

Este documento define la arquitectura de carpetas y la distribución lógica de responsabilidades (Separation of Concerns) del proyecto. 

La organización sigue un patrón modular basado en dominios, garantizando la escalabilidad desde la ingesta de datos crudos hasta el despliegue del agente orquestador.

```text
.
├── backend/
│   ├── api/
│   │   ├── main.py            # Punto de entrada (uvicorn), logging, carga de .env
│   │   ├── api.py             # App FastAPI: lifespan, /health, /ready, /metrics
│   │   ├── schemas/           # DTOs Pydantic del dominio (Fase 3-4)
│   │   └── metrics/           # Métricas in-memory básicas
│   ├── db/
│   │   ├── base.py            # Base declarativa de SQLAlchemy
│   │   ├── models.py          # Modelos ORM (Distritos, Barrios, Competidores GIS)
│   │   └── connection.py      # Inyección dinámica de URL de conexión (Docker/Local)
│   ├── etl/
│   │   ├── config.py          # Gestión de rutas portables (data/raw, data/processed)
│   │   ├── income.py          # Pipelines de Renta media (fuente: INE)
│   │   ├── mobility.py        # Pipelines de Afluencia peatonal (fuente: MITMA)
│   │   └── competitors.py     # Normalización geoespacial de competidores hosteleros
│   ├── rag/
│   │   ├── chunking.py        # Estrategia de fragmentación de normativa legal
│   │   ├── pdf_extraction.py  # Extracción OCR/Texto de PDF (pdftotext)
│   │   ├── embeddings.py      # Generación vectorial local (sentence-transformers)
│   │   └── query_engine.py    # Recuperación (pgvector) + Generación (Claude)
│   ├── ia/
│   │   └── agent.py           # Orquestador LangGraph (Fusiona Datos + RAG)
│   └── requirements.txt       # Manifiesto estricto de dependencias
│
├── database/
│   ├── alembic.ini            # Configuración del motor de migraciones
│   ├── alembic/
│   │   ├── env.py             # Puente entre Alembic y la base de datos
│   │   └── versions/          # Historial de migraciones SQL
│   ├── load_to_db.py          # ETL Master: Sociodemográfico -> Postgres
│   └── load_legal_corpus.py   # ETL Master: Normativa -> Embeddings -> Postgres
│
├── data/                      # Almacén de datos (ignorado en Git por seguridad)
│   ├── raw/                   # Ficheros inmutables de origen
│   └── processed/             # Salidas intermedias y modelos entrenados
│
├── notebooks/                 # Entornos Jupyter para Análisis Exploratorio (EDA)
│
├── frontend/                  # Aplicación cliente (Vue 3 + Vite)
│
├── deployment/
│   ├── Dockerfile             # Receta de empaquetado de la API
│   ├── docker-compose.yml     # Orquestador de infraestructura local
│   └── .dockerignore          # Filtro de seguridad para el Build Context
│
├── docs/
│   ├── structure.md           # (Este documento) Mapa de arquitectura
│   ├── data-sources.md        # Catálogo de fuentes y linaje de datos
│   ├── diagram.md             # Representación Mermaid (Data Flow)
│   └── adr/                   # Registros formales de decisiones arquitectónicas
│
├── tests/
│   ├── conftest.py            # Fixtures globales (ej: inyección de base de datos)
│   ├── unit_tests/            # Pruebas unitarias de aislamiento rápido
│   └── model_tests/           # Pruebas de integración del agente IA
│
├── .github/workflows/
│   ├── integrate.yml          # CI: Tests automáticos en Pull Requests
│   ├── check-branch.yml       # Gobernanza: Validación de políticas Git-Flow
│   └── deploy.yml             # CD: Despliegue continuo hacia producción
│
├── .env.example               # Plantilla de secretos (Single Source of Truth)
└── README.md
```

## Principios de Diseño y Operaciones Frecuentes

- **Single Source of Truth (SSOT) para Secretos:**
  Un único archivo `.env` en la raíz gobierna todo el proyecto. Servicios como Docker (`env_file`) o Alembic leen directamente de él, evitando la fragmentación y desincronización de credenciales.

- **Resolución de Módulos (Namespace):**
  El paquete raíz de Python es `backend`. Todas las ejecuciones deben lanzarse desde la raíz del repositorio usando el flag de módulo (`-m`), garantizando que las importaciones relativas funcionen idénticamente en local y en Docker (Ej: `python -m backend.api.main`).

- **Jerarquía Geoespacial Estricta (Fase 1):**
  El modelo de datos respeta la granularidad: `District` (Estático, Nivel 1) → `Neighborhood` (Dinámico del Censo, Nivel 2) → `Competitor` (Geometría de Puntos, Nivel 3).

- **Materialización de Datos (Vistas vs Tablas):**
  El tablero de puntuación (`district_scorecard`) está diseñado como una **Vista SQL** en lugar de una tabla física. Esto garantiza que el cálculo del `Opportunity_Score` sea dinámico y nunca sufra desincronización respecto a los datos subyacentes de renta, movilidad y saturación de competidores.

- **Comandos de Gestión de Base de Datos:**
  - *Migraciones:* `DB_HOST_OVERRIDE=localhost alembic -c database/alembic.ini upgrade head`
  - *Carga ETL:* `DB_HOST_OVERRIDE=localhost python -m database.load_to_db`
  
  *(Nota: La variable `DB_HOST_OVERRIDE` inyecta dinámicamente la resolución `localhost` permitiendo ejecutar operaciones desde el host hacia el contenedor Docker).*