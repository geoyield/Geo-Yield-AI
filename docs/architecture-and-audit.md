# 🌍 Geo-Yield-AI: Documentación de Arquitectura y Auditoría

Este documento resume la arquitectura técnica, las decisiones de diseño y la estructura de archivos de **Geo-Yield-AI**, una plataforma SaaS de Location Intelligence basada en un Agente de IA Autónomo.

## 🚀 Resumen Ejecutivo por Fases

Antes de construir nada nuevo, el proyecto pasó por una **Fase 0 de auditoría**: el repositorio de partida mezclaba trabajo real (los notebooks de análisis de datos) con restos de un ejercicio anterior del máster sin relación con el producto (un endpoint que servía un modelo de scikit-learn genérico, plantillas de CRUD de "tareas", dos READMEs con estructuras de proyecto contradictorias). Esa fase se dedicó a separar ambas cosas, corregir la infraestructura base (Docker, CI/CD) y dejar una única base de código coherente sobre la que construir.

A partir de ahí, el proyecto está dividido en tres grandes bloques que trabajan en conjunto:

*   **Fase 1 (El Cerebro Analítico - Datos Geoespaciales):** Se encarga de entender *dónde* estamos. Recoge datos de movilidad (MITMA), renta (INE) y censo comercial (Ayuntamiento). Limpia estos datos, los cruza y asigna un "Índice de Oportunidad" del 0 al 100 a cada distrito.
*   **Fase 2 (El Abogado Virtual - Motor RAG Legal):** Procesa los PDFs de normativas urbanísticas (PGM). Divide el texto por artículos, descarta versiones derogadas y convierte el texto vigente en vectores (embeddings locales). Permite buscar la ley exacta aplicable y usar un LLM (Gemini) para redactar una respuesta basada *estrictamente* en ese contexto.
*   **Fase 3 (El Orquestador General - Agente LangGraph):** Es el director de la orquesta. Recibe la petición del usuario, consulta simultáneamente los datos sociodemográficos (Fase 1) y las normativas legales (Fase 2). Finalmente, un modelo de IA sintetiza todo en un informe claro con un veredicto visual: Semáforo **VERDE, ÁMBAR o ROJO**.

---

## 🕵️‍♂️ Auditoría de Código (Code Review)

El proyecto presenta una arquitectura de nivel Senior, destacando por las siguientes decisiones técnicas:

*   **Gestión de Concurrencia (Thread-Safety):** El uso de `LangGraph` para ejecutar nodos en paralelo (`datos_socioeconomicos` y `normativa_legal`) se maneja abriendo sesiones de base de datos independientes, evitando la corrupción de la `Session` compartida de SQLAlchemy. Este no fue un diseño anticipado sobre el papel: apareció como un error real de concurrencia al ejecutar el grafo por primera vez, y se corrigió dándole a cada nodo paralelo su propia sesión en vez de simplificar el diseño a uno secuencial.
*   **Búsqueda Híbrida Real:** Uso de `pgvector` para combinar filtros estructurados SQL (ej. `WHERE zona_pgm = X`) con búsqueda de similitud coseno. Esto elimina las "alucinaciones" del motor RAG garantizando precisión legal.
*   **Vistas Dinámicas vs Tablas Estáticas:** El `opportunity_score` se calcula en tiempo real mediante la vista SQL `district_scorecard`, previniendo la desincronización de datos si los pesos del algoritmo cambian en el futuro.
*   **PostGIS `Geography`:** Implementación del tipo `Geography(POINT, 4326)` en lugar de `Geometry`, permitiendo cálculos directos de distancia en metros a nivel de base de datos.
*   **Decisión de Arquitectura Documentada (ADR):** La elección de `pgvector` sobre una base de datos vectorial dedicada (Qdrant) no fue por defecto, sino una decisión evaluada y documentada (`docs/adr/0001-pgvector-vs-qdrant.md`): a la escala del MVP, tener los datos geoespaciales y los vectores legales en el mismo motor permite consultas híbridas en una sola transacción, con menos infraestructura que operar.
*   **Desarrollo Guiado por Infraestructura Real:** La mayoría de los bugs del proyecto no se encontraron leyendo código, sino ejecutándolo contra infraestructura real (Postgres+PostGIS+pgvector en contenedor, PDFs reales del Ajuntament de Barcelona, el modelo de embeddings real, y dos proveedores de LLM reales). Ejemplos concretos: una migración que asumía que la extensión `pgvector` ya estaba instalada; un parser de PDF que descartaba en silencio la versión *vigente* de un artículo legal (quedándose con la derogada) porque su título se partía en dos líneas al extraer el texto; un `id_global` real de 37 caracteres que rompía una columna diseñada para 36 (el largo de un UUID estándar).
*   **Migraciones con Disciplina de Versionado:** Nunca se edita una migración ya aplicada. Cuando un dato real no encajaba en el esquema (el caso del `id_global` de 37 caracteres), se creó una migración nueva encima, preservando el historial en vez de reescribirlo.
*   **Inyección de Dependencias para Testabilidad:** Tanto la función de embeddings como el cliente del LLM son parámetros inyectables en todo el pipeline (`embed_fn`, `llm_client`). Esto permite testear la lógica de negocio (recuperación, construcción del prompt, parseo de la respuesta) sin gastar cuota de API real ni depender de tener un modelo descargado — la suite de tests corre igual de bien con o sin conexión a internet.
*   **Filtrado Legal Explícito, no Inferido:** La zona urbanística (PGM) que aplica a una consulta la elige el usuario explícitamente, en vez de inferirla automáticamente del distrito. Un mismo distrito administrativo puede abarcar varias zonas PGM distintas, y sin datos geoespaciales reales del planeamiento no había forma honesta de adivinar la zona correcta — se priorizó la precisión legal sobre la comodidad de la interfaz.
*   **Interfaz de LLM Desacoplada del Proveedor:** El motor RAG llama al LLM a través de una interfaz común (`.messages.create(...)`), no directamente contra el SDK de un proveedor concreto. Esto se probó primero con dos proveedores en paralelo (Claude y un adaptador de Gemini) durante el desarrollo, y cuando se tomó la decisión definitiva de usar Gemini para el MVP, el cambio se limitó a los valores por defecto — ningún módulo que consume el LLM tuvo que reescribirse.

---

## 🗺️ Mapa de Archivos (Estructura del Proyecto)

A continuación, se detalla la responsabilidad de los archivos principales del repositorio:

### Configuración Global e Infraestructura
*   `.env.example`: Plantilla de credenciales y variables de entorno del sistema.
*   `.gitignore` / `pytest.ini`: Reglas de exclusión de Git y configuración de la suite de tests (rutas de import, sin necesidad de `PYTHONPATH` manual).
*   `.github/workflows/*`: Pipelines de CI/CD (validación de reglas Git-Flow, tests automáticos y despliegue en Render).
*   `deployment/Dockerfile` & `Dockerfile.postgis`: Recetas de Docker para la API y la base de datos (Postgres 18 + PostGIS + pgvector, instalados vía el repositorio oficial de PostgreSQL — la imagen oficial de PostGIS no incluye pgvector).
*   `deployment/docker-compose.yml`: Orquestador de contenedores para levantar el entorno de desarrollo local, con reinicio automático de los servicios.

### Backend Principal (API)
*   `backend/api/main.py`: Punto de entrada principal de la aplicación web (`uvicorn`).
*   `backend/api/api.py`: Configuración de FastAPI, gestión del ciclo de vida (lifespan) y endpoints base (`/health`, `/ready`, `/metrics`).
*   `backend/api/schemas/schema.py`: Definición de los DTOs (Data Transfer Objects) para la validación de entrada/salida de la API.
*   `backend/api/metrics/metrics.py`: Métricas básicas de observabilidad (conteo de peticiones).

### Fase 1: Base de Datos y ETL
*   `backend/db/models.py`: Definición ORM de las tablas (Distritos, Barrios, Competidores, Renta, Movilidad y Chunks Legales).
*   `backend/db/base.py`: Base declarativa de SQLAlchemy compartida por todos los modelos.
*   `backend/db/connection.py`: Helper de red para resolver la cadena de conexión a la BD dentro y fuera de Docker.
*   `backend/etl/*`: Scripts de extracción, limpieza y transformación de datos brutos (MITMA, INE, censo comercial de Barcelona).
*   `database/load_to_db.py`: Orquestador maestro que ejecuta el ETL y guarda los datos limpios en PostGIS.
*   `database/alembic/`: Historial inmutable de migraciones de esquema de la base de datos (`env.py` resuelve la conexión; `versions/` contiene cada cambio de esquema como fichero independiente y nunca editado retroactivamente).

### Fase 2: Motor RAG (Inteligencia Legal)
*   `backend/rag/pdf_extraction.py` & `chunking.py`: Lógica de extracción de texto de PDFs y división estructurada por artículos vigentes, con tolerancia a las inconsistencias reales del texto de origen.
*   `backend/rag/embeddings.py`: Generador de embeddings locales de coste cero (`sentence-transformers`).
*   `backend/rag/query_engine.py`: Motor de búsqueda semántica híbrida (filtro exacto de zona + similitud coseno) y generación de respuestas usando el LLM.
*   `backend/rag/gemini_adapter.py`: Adaptador que expone la API de Gemini (proveedor de LLM definitivo del MVP) con la misma interfaz que un cliente Anthropic-shaped, para que el resto del pipeline sea agnóstico al proveedor.
*   `database/load_legal_corpus.py`: Script para cargar, vectorizar y persistir la normativa en la base de datos vectorial, clasificando cada artículo por zona urbanística (PGM).

### Fase 3: Agente Orquestador
*   `backend/ia/agent.py`: Grafo de estado de `LangGraph` que coordina los datos de la Fase 1 y Fase 2 (en paralelo) para emitir el informe de viabilidad final estructurado.

### Documentación
*   `docs/structure.md`: Estructura vigente del repositorio, mantenida al día en cada fase.
*   `docs/adr/0001-pgvector-vs-qdrant.md`: Registro formal de la decisión de arquitectura del motor vectorial.
*   `docs/diagram.md`: Diagrama de arquitectura de alto nivel.

### Tests (Control de Calidad)
*   `tests/conftest.py`: Fixture compartida `db_session`, que se salta con gracia (no falla) cuando no hay una base de datos real disponible — protege la integración continua sin sacrificar el valor de los tests contra infraestructura real cuando sí la hay.
*   `tests/unit_tests/*`: Batería de tests que verifican la resiliencia del ETL, el chunking legal, el motor RAG, el adaptador de Gemini y el agente — incluyendo regresiones específicas para cada bug real encontrado durante el desarrollo.

---

## ✅ Resultados y Validación

El sistema no se quedó en el diseño: se probó de extremo a extremo con datos e infraestructura reales en cada fase.

*   **Datos reales cargados:** 11.097 locales de hostelería, 73 barrios y los 10 distritos de Barcelona (Fase 1); normativa vigente del PGM para tres zonas urbanísticas — nucli antic, densificació urbana e industrial — ampliable a medida que se ingieran más artículos (Fase 2).
*   **Validación de negocio, no solo técnica:** el ranking de oportunidad por distrito coincide con lo conocido de Barcelona (Sarrià-Sant Gervasi arriba por renta y baja saturación; Ciutat Vella abajo por saturación turística pese a tener afluencia).
*   **Consulta real de extremo a extremo:** ante la pregunta *"¿Puedo abrir un bar en una zona industrial?"*, el sistema recupera semánticamente el Artículo 311 (sin que nadie le indique el número) y responde citándolo con precisión, incluyendo el apartado exacto.
*   **Suite de tests:** 43 tests automatizados, cubriendo desde el parseo de PDFs reales hasta la orquestación completa del agente.

---

## 🔭 Próximos Pasos

*   Exponer el agente (`backend/ia/agent.py`) como endpoint de la API (`backend/api/api.py`), hoy invocable solo como módulo Python.
*   Ampliar el corpus legal más allá de los tres artículos iniciales, cubriendo el resto de zonas del PGM.
*   Desarrollo del frontend (Vue.js) para la interacción del usuario final.