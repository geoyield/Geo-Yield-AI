# ADR 0001: Motor de base de datos vectorial — pgvector vs. Qdrant

**Estado:** Aceptada
**Fecha:** Fase 0 del proyecto

## Contexto

El motor RAG legal de Geo-Yield-AI necesita almacenar y consultar embeddings
de fragmentos de normativa urbanística (PGOU) para recuperar contexto
relevante en cada informe de viabilidad. Se evaluaron dos opciones:

1. **PostgreSQL + pgvector**, sobre la misma instancia de Supabase
   (Postgres/PostGIS) que ya aloja los datos sociodemográficos y geoespaciales.
2. **Qdrant**, como base de datos vectorial dedicada y separada.

## Decisión

Se usará **pgvector sobre la misma base de datos Postgres/PostGIS** para el
MVP.

## Justificación

- **La feature diferencial del producto es el cruce entre normativa
  (vectorial) y geografía/demografía (relacional/espacial).** Con pgvector,
  una consulta puede combinar en una sola transacción SQL un filtro
  geoespacial/demográfico con una búsqueda por similitud semántica (p. ej.
  "artículos relevantes para 'licencia de terraza' Y que apliquen al
  distrito X"). Con Qdrant + Postgres separados, esa combinación exige
  orquestar dos sistemas y sincronizar identificadores entre ambos.
- **Ya existe una dependencia dura de PostGIS** para los datos
  sociodemográficos (secciones censales, distritos, competidores
  geolocalizados). Esa base de datos existe de todas formas.
- **Volumen del MVP:** normativa de una ciudad piloto (Barcelona) — del
  orden de miles de chunks, no millones. El índice HNSW de pgvector rinde
  perfectamente a esa escala; el problema que resuelve Qdrant (escala muy
  alta, QPS elevado, filtrado avanzado sobre payloads) no existe todavía en
  este proyecto.
- **Menos infraestructura que operar** con un equipo de 4 personas y un
  plazo de máster: una única base de datos que provisionar, respaldar y
  asegurar, en vez de dos sistemas distintos.
- **Ya está en la dirección declarada del proyecto** (README, variables de
  entorno de Supabase) — valida y no contradice el rumbo ya tomado por el
  equipo.
- LlamaIndex tiene integración de primera clase (`PGVectorStore`), sin
  fricción de framework.

## Consecuencias

- La extensión `pgvector` deberá habilitarse en la instancia de Supabase
  (`CREATE EXTENSION IF NOT EXISTS vector;`), tarea de la Fase 2.
- Todo el tráfico de escritura/lectura de embeddings comparte recursos con
  el tráfico transaccional/geoespacial. A la escala del MVP esto no es un
  problema; si se convierte en cuello de botella, es una señal concreta
  para revisar esta decisión.

## Cuándo revisar esta decisión

Migrar a Qdrant (u otra base de datos vectorial dedicada) si ocurre
cualquiera de estos escenarios, típicamente post-MVP:

- El corpus normativo escala a múltiples ciudades y alcanza millones de
  chunks.
- Se necesitan latencias de retrieval muy agresivas a alta concurrencia.
- Se necesita filtrado avanzado sobre payloads o cuantización que pgvector
  no ofrece de forma nativa.
- El escalado del motor vectorial necesita desacoplarse del escalado de la
  carga transaccional/geoespacial.
