# GEO-YIELD-AI

**Geo-Yield-AI** es una plataforma SaaS de *Location Intelligence* diseñada para transformar la toma de decisiones en la expansión de cadenas de retail, negocios, franquicias y consultoras inmobiliarias. 

Utilizamos un enfoque de **Agente de IA Autónomo** que combina Big Data de movilidad, análisis sociodemográfico y validación normativa instantánea mediante arquitectura RAG.

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
Abrir un nuevo local comercial conlleva un alto riesgo financiero. Las decisiones suelen basarse en intuiciones o estudios de mercado lentos (semanas) y costosos, que a menudo ignoran las complejas normativas urbanísticas locales (PGOU).

### La Solución
**Geo-Yield-AI** actúa como un consultor inmobiliario 360° que reduce el tiempo de evaluación de semanas a segundos:
* **Validación Hiper-Local:** Mapas de calor de afluencia peatonal real.
* **Inteligencia Legal:** Interpretación automática de leyes urbanas para confirmar la viabilidad de licencias.
* **Análisis de Mercado:** Perfilado demográfico y mapeo de la competencia.

---

## ✨ Características Principales

1. **Análisis de Movilidad Dinámica:** Procesamiento de Big Data del **MITMA** (Ministerio de Transportes) para identificar flujos de personas.
2. **Motor RAG Legal:** Uso de **LlamaIndex** y **pgvector** para consultar normativas urbanísticas sin alucinaciones.
3. **Perfilado Sociodemográfico:** Filtros por niveles de renta, edad y densidad de población a nivel de barrio (Open Data BCN, 73 barrios).
4. **Mapeo de la Competencia:** Censo de locales comerciales (Open Data BCN) y puntos de interés de hostelería (OSM: cafeterías, bares, restaurantes) para densidad de competidores.
5. **Semáforo de Viabilidad:** Informe ejecutivo (Verde/Ámbar/Rojo) sobre la factibilidad técnica y legal.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
| :--- | :--- |
| **Lenguaje** | Python 3.10+ |
| **IA / RAG** | LlamaIndex, OpenAI GPT-4o / Claude 3.5 |
| **Backend** | FastAPI |
| **Frontend** | Vue.js (Mapas interactivos) |
| **Base de Datos** | Supabase (PostgreSQL/PostGIS + pgvector) |
| **Data Science** | Pandas, GeoPandas |
| **DevOps** | Docker, GitHub Actions, CI/CD |

---

## 🏗️ Arquitectura del Sistema

El flujo de datos sigue una estructura **Cloud-Native**:
1. **Ingesta:** Carga de datasets MITMA, del INE, del GenCAT y PDFs normativos.
2. **Procesamiento:** Normalización con GeoPandas y creación de embeddings.
3. **Orquestación:** FastAPI coordina las peticiones del usuario con el motor RAG.
4. **Veredicto:** El LLM genera un informe basado en el contexto recuperado de la base vectorial.

---

## 📂 Estructura del repositorio (monorepo)

```
.
├── apps/
│   └── api/                 # FastAPI: endpoints de movilidad, demografía, competencia y POIs
│       ├── app/
│       │   ├── main.py      # /health, /zones, /mobility/*, /neighborhoods, /competitors, /demographics/*, /pois, /catastro/parcel
│       │   ├── catastro.py   # cliente del webservice OVC del Catastro (lookup en vivo)
│       │   └── db.py         # conexión SQLAlchemy a Postgres (DATABASE_URL)
│       ├── Dockerfile
│       └── requirements.txt
├── infra/
│   └── db/                  # Postgres con esquema inicial
│       ├── Dockerfile
│       └── init/
│           ├── 001_schema.sql        # zones, mobility_flows_hourly, zone_population_daily, ingestion_state
│           ├── 002_opendata_bcn.sql  # neighborhoods, commercial_premises, population_by_neighborhood, income_by_neighborhood
│           └── 003_osm_pois.sql      # osm_pois
├── ingestion/               # Scripts locales (no dockerizados) para descarga/carga de datos
│   ├── common.py
│   ├── download_mitma_data.py    # movilidad MITMA (Barcelona, por-distritos)
│   ├── load_mitma_data.py
│   ├── download_opendata_bcn.py  # censo comercial, padró y renda (Open Data BCN, por barrio)
│   ├── load_opendata_bcn.py
│   ├── download_osm_pois.py      # cafeterías/bares/restaurantes (OSM Overpass API)
│   ├── load_osm_pois.py
│   └── requirements.txt
├── data_raw/                # Ficheros descargados (ignorado por git)
├── docker-compose.yml       # Servicios: db (con volumen) + api
└── .env.example
```

## 🚀 Instalación y Uso

### Requisitos previos
* Docker y Docker Compose
* Python 3.10+ (para los scripts de `ingestion/`)

### 1. Levantar la API y la base de datos

```bash
cp .env.example .env
docker compose up --build
```

* `api` queda disponible en `http://localhost:8080`:
  * **Movilidad (MITMA):** `/zones`, `/mobility/flows`, `/mobility/population`
  * **Barrios y competencia (Open Data BCN):** `/neighborhoods`, `/competitors`, `/demographics/population`, `/demographics/income`
  * **Puntos de interés (OSM):** `/pois`
  * **Catastro (lookup en vivo):** `/catastro/parcel?lat=&lon=` — referencia catastral, uso, superficie total, año de construcción y desglose por unidades del edificio en esas coordenadas, vía el webservice OVC de la Sede Electrónica del Catastro (sin necesidad de API key ni descarga previa).
  * `/health`
* `db` (Postgres 16) expone el puerto `5433` (host) → `5432` (contenedor) y persiste los datos en el volumen `pgdata`, por lo que `docker compose down` / reinicios no pierden información. Solo `docker compose down -v` borra el volumen.
* El esquema se crea automáticamente al primer arranque desde `infra/db/init/` (`001_schema.sql`, `002_opendata_bcn.sql`, `003_osm_pois.sql`).

### 2. Descargar datos de movilidad de MITMA (Barcelona)

Con la base de datos levantada (puerto 5433 expuesto en `localhost`):

```bash
cd ingestion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Descarga el último mes completo de "viajes" y "personas"
# (por-distritos) a ../data_raw/, sin filtrar (~7 GB)
python download_mitma_data.py --months 1

# Filtra a los 10 distritos de Barcelona, agrega y carga en Postgres
python load_mitma_data.py
```

Ambos scripts son idempotentes: `download_mitma_data.py` no re-descarga ficheros existentes en `data_raw/`, y `load_mitma_data.py` registra cada fichero procesado en `ingestion_state` (usa `--force` para recargar).

Cada mes adicional añade ~7 GB a `data_raw/`. `--months 1` ya cubre un mes completo de patrones horarios de movilidad y población diaria, suficiente para las features actuales; aumenta `--months` solo si vas a explotar tendencias mensuales/estacionales.

### 3. Descargar datos de Open Data BCN y OSM (barrios, competencia, POIs)

Con la base de datos levantada y el entorno virtual de `ingestion/` activado:

```bash
cd ingestion

# Censo comercial, padró (población) y renda por barrio (73 barrios de Barcelona)
python download_opendata_bcn.py
python load_opendata_bcn.py

# Cafeterías, bares, restaurantes, fast food y pubs (Overpass API / OSM)
python download_osm_pois.py
python load_osm_pois.py
```

Ambos pares de scripts son idempotentes: los `download_*.py` no vuelven a descargar ficheros ya presentes en `data_raw/`, y los `load_*.py` cargan un snapshot completo (truncan y recargan las tablas correspondientes en cada ejecución). Estos datasets ya vienen acotados a Barcelona, sin necesidad de filtrado adicional.

## 🔄 DevOps y Despliegue
Este proyecto aplica los conocimientos de ingeniería adquiridos en el Máster:

    - Contenedores: Imagen Docker para asegurar que el entorno de desarrollo sea idéntico al de producción.

    - CI/CD: Pipelines en GitHub Actions para despliegue automático en Render o Railway.

    - Observabilidad: Monitorización básica de latencias en las llamadas al LLM.

## 👥 Equipo
Proyecto desarrollado por 4 compañeros del Máster en IA, Cloud y DevOps (Pontia):
    - Manuel Yerbes García
    - Marvin Bernal
    - Enmanuel De Oleo
    - Claudi Berenguer Sabaté