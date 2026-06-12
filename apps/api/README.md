# Geo-Yield-AI API

FastAPI service exposing Barcelona mobility, demographic, competitor, points-of-interest and cadastral data as JSON over HTTP.

## Requisitos previos

* Docker y Docker Compose, **o** Python 3.11+ si quieres ejecutarlo sin contenedores.
* Una base de datos Postgres con el esquema y los datos cargados (ver [`ingestion/`](../../ingestion) y el [README principal](../../README.md)). La mayoría de endpoints devuelven listas vacías si las tablas correspondientes no se han poblado todavía.

## Opción 1: Docker Compose (recomendado)

Desde la raíz del repositorio:

```bash
cp .env.example .env
docker compose up --build
```

Esto levanta `db` (Postgres 16, puerto `5433` en el host) y `api` (puerto `8080`), con el esquema inicial aplicado automáticamente desde `infra/db/init/`.

Para reconstruir solo la API tras un cambio de código:

```bash
docker compose up --build -d api
```

## Opción 2: Ejecución local sin Docker

Requiere una Postgres accesible (por ejemplo, la del `docker compose` anterior expuesta en `localhost:5433`).

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/geoyield
uvicorn app.main:app --reload --port 8080
```

## Variables de entorno

| Variable | Default | Descripción |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://postgres:postgres@db:5432/geoyield` | Cadena de conexión SQLAlchemy/psycopg2 a Postgres. El default asume el nombre de servicio `db` de docker-compose; en ejecución local hay que sobreescribirla (puerto `5433`). |

El endpoint `/catastro/parcel` no requiere configuración adicional: llama en vivo al webservice público OVC de la Sede Electrónica del Catastro (sin API key).

## Endpoints

| Endpoint | Descripción |
| :--- | :--- |
| `GET /health` | Comprobación de estado. |
| `GET /zones` | Distritos MITMA (`barcelona_only=true` por defecto filtra a los 10 distritos de Barcelona). |
| `GET /mobility/flows` | Flujos de viajes hora a hora (MITMA). Filtros: `zone_id`, `date_from`, `date_to`, `hour`, `limit`. |
| `GET /mobility/population` | Población diaria por zona (MITMA). Filtros: `zone_id`, `date_from`, `date_to`, `limit`. |
| `GET /neighborhoods` | Los 73 barrios de Barcelona (Open Data BCN), con su distrito. |
| `GET /competitors` | Censo de locales comerciales (Open Data BCN). Filtros: `neighborhood_code`, `activity_group`, `active_only` (default `true`), `limit`. |
| `GET /demographics/population` | Población por barrio/edad/sexo (padró). Filtros: `neighborhood_code`, `limit`. |
| `GET /demographics/income` | Renta disponible per cápita por barrio (RFD). Filtros: `neighborhood_code`, `limit`. |
| `GET /points-of-interest` | Puntos de interés de hostelería (OSM: cafés, bares, restaurantes, fast food, pubs). Filtros: `category`, `limit`. |
| `GET /catastro/parcel?lat=&lon=` | Lookup en vivo en el Catastro: referencia catastral, uso, superficie total, año de construcción y desglose por unidades del edificio en esas coordenadas. Devuelve `404` si no hay parcela en esa ubicación. |

### Ejemplos

```bash
curl "http://localhost:8080/neighborhoods"
curl "http://localhost:8080/competitors?neighborhood_code=1&activity_group=Restauració"
curl "http://localhost:8080/demographics/income?neighborhood_code=1"
curl "http://localhost:8080/points-of-interest?category=cafe"
curl "http://localhost:8080/catastro/parcel?lat=41.3851&lon=2.1734"
```

La documentación interactiva (Swagger UI) está disponible en `http://localhost:8080/docs`.
