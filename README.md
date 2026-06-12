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
│   └── api/                 # FastAPI: endpoints de movilidad, demografía, competencia y POIs (ver apps/api/README.md)
│       ├── app/
│       │   ├── main.py      # /health, /zones, /mobility/*, /neighborhoods, /competitors, /demographics/*, /points-of-interest, /catastro/parcel
│       │   ├── catastro.py   # cliente del webservice OVC del Catastro (lookup en vivo)
│       │   └── db.py         # conexión SQLAlchemy a Postgres (DATABASE_URL)
│       ├── Dockerfile
│       ├── README.md
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

Guía completa para levantar el proyecto **en local**: base de datos + API + carga de todos los datasets.

### Requisitos previos
* [Docker](https://docs.docker.com/get-docker/) y Docker Compose (incluidos en Docker Desktop).
* Python 3.10+ con `venv`, para los scripts de `ingestion/` (se ejecutan en el host, **no** están dockerizados).
* `curl` para probar la API (o usa el Swagger UI, ver paso 5).
* ~500 MB de espacio libre en disco para `data_raw/`.

### Resumen rápido (TL;DR)

```bash
# 1. Variables de entorno
cp .env.example .env

# 2. Levantar Postgres + API
docker compose up --build -d
curl http://localhost:8080/health   # -> {"status":"ok"}

# 3. Cargar todos los datasets (entorno virtual de ingestion/)
cd ingestion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python download_mitma_data.py --months 1 && python load_mitma_data.py
python download_opendata_bcn.py && python load_opendata_bcn.py
python download_osm_pois.py && python load_osm_pois.py
cd ..

# 4. Probar un endpoint con datos
curl "http://localhost:8080/neighborhoods" | head -c 300
```

A continuación se explica cada paso en detalle.

### 1. Clonar el repositorio y configurar variables de entorno

```bash
git clone <url-del-repo>
cd Geo-Yield-AI
cp .env.example .env
```

`.env.example` ya trae valores válidos para desarrollo local (usuario/contraseña `postgres`, puerto host `5433`, etc.). No es necesario editarlo salvo conflicto de puertos.

### 2. Levantar la base de datos y la API

```bash
docker compose up --build -d
```

Esto construye y arranca dos contenedores:

| Servicio | Origen | Puerto host → contenedor | Descripción |
| :--- | :--- | :--- | :--- |
| `db` | `infra/db` (Postgres 16) | `5433` → `5432` | Esquema inicial aplicado automáticamente al primer arranque desde `infra/db/init/` (`001_schema.sql`, `002_opendata_bcn.sql`, `003_osm_pois.sql`). Datos persistidos en el volumen `pgdata`. |
| `api` | `apps/api` (FastAPI) | `8080` → `8080` | Ver [apps/api/README.md](apps/api/README.md) para el detalle de cada endpoint. |

Comprueba que ambos servicios están arriba y la API responde:

```bash
docker compose ps
curl http://localhost:8080/health
# -> {"status":"ok"}
```

> ⚠️ En este punto la API ya responde, pero las tablas de datos están **vacías**: `/zones`, `/neighborhoods`, `/competitors`, `/points-of-interest`, etc. devolverán `[]` hasta completar el paso 4. `/catastro/parcel` es la excepción: funciona desde ya porque consulta el Catastro en vivo.

Comandos útiles:

```bash
docker compose logs -f api      # logs en vivo de la API
docker compose down             # parar (conserva los datos del volumen pgdata)
docker compose down -v          # parar y borrar también el volumen (reset completo de la BD)
```

### 3. Preparar el entorno de ingesta (Python)

Los scripts de `ingestion/` descargan los datasets y los cargan en Postgres. Se ejecutan en el **host** (no están dockerizados) y necesitan que `db` esté levantado y accesible en `localhost:5433`.

```bash
cd ingestion
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Por defecto los scripts se conectan a `postgresql://postgres:postgres@localhost:5433/geoyield` (coherente con `.env.example`). Si cambiaste `POSTGRES_HOST_PORT` o las credenciales, exporta `DATABASE_URL` antes de ejecutar cualquier script:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/geoyield
```

### 4. Cargar los datasets

Con el entorno virtual activado y `cd ingestion`, ejecuta en orden:

#### 4.1 Movilidad MITMA (Barcelona)

```bash
# Descarga el último mes completo de "viajes" y "personas" (por-distritos),
# filtrando a las filas relacionadas con Barcelona durante la descarga (~280 MB)
python download_mitma_data.py --months 1

# Agrega por hora/día y carga en Postgres
python load_mitma_data.py
```

#### 4.2 Open Data BCN (barrios, censo comercial, población, renta)

```bash
# Censo comercial, padró (población) y renta por barrio (73 barrios de Barcelona, ~27 MB)
python download_opendata_bcn.py
python load_opendata_bcn.py
```

#### 4.3 OSM (puntos de interés de hostelería)

```bash
# Cafeterías, bares, restaurantes, fast food y pubs vía Overpass API (~2 MB)
python download_osm_pois.py
python load_osm_pois.py
```

Notas:
* Todos los `download_*.py` son idempotentes: no vuelven a descargar ficheros ya presentes en `data_raw/`.
* `load_mitma_data.py` registra cada fichero procesado en `ingestion_state` y solo lo recarga si usas `--force`. Los demás `load_*.py` truncan y recargan sus tablas en cada ejecución (son snapshots completos).
* `download_osm_pois.py` llama a la API pública de Overpass, que en ocasiones devuelve `504 Gateway Timeout` bajo carga. Si falla, vuelve a ejecutar el mismo comando.

### 5. Verificar que los datos están cargados

```bash
curl "http://localhost:8080/zones"
curl "http://localhost:8080/neighborhoods"
curl "http://localhost:8080/competitors?neighborhood_code=1&limit=5"
curl "http://localhost:8080/demographics/population?neighborhood_code=1&limit=5"
curl "http://localhost:8080/demographics/income?neighborhood_code=1"
curl "http://localhost:8080/points-of-interest?category=cafe&limit=5"
curl "http://localhost:8080/mobility/flows?limit=5"
curl "http://localhost:8080/catastro/parcel?lat=41.3851&lon=2.1734"
```

También puedes explorar y probar todos los endpoints de forma interactiva en **`http://localhost:8080/docs`** (Swagger UI).

### 6. Reiniciar / reset completo

```bash
docker compose down -v      # borra el volumen de Postgres (esquema y datos)
docker compose up --build -d

cd ingestion && source .venv/bin/activate
# data_raw/ ya tiene los ficheros descargados, no hace falta volver a descargar
python load_mitma_data.py
python load_opendata_bcn.py
python load_osm_pois.py
```

### Solución de problemas

| Problema | Causa / solución |
| :--- | :--- |
| `bind: address already in use` en `5433` u `8080` | Otro proceso usa ese puerto. Cambia `POSTGRES_HOST_PORT` en `.env`, o detén el proceso que lo ocupa. |
| Los endpoints devuelven `[]` | La tabla correspondiente está vacía. Revisa que los `load_*.py` del paso 4 se ejecutaron sin errores. |
| `download_osm_pois.py` → `504 Gateway Timeout` | La API pública de Overpass está saturada; reintenta el mismo comando. |
| Error de conexión en los scripts de `ingestion/` | Comprueba que `docker compose ps` muestra `db` como `running` y que `DATABASE_URL`/puerto `5433` son correctos. |
| `docker compose up` falla al construir | Asegúrate de que Docker (Desktop) está corriendo y de tener permisos sobre el directorio del proyecto. |

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