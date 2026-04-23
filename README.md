# Contenido para el archivo README.md
readme_content = """# LocateIQ (formerly Geo-Yield AI) 🚀

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
3. **Perfilado Sociodemográfico:** Filtros por niveles de renta, edad y densidad de población.
4. **Semáforo de Viabilidad:** Informe ejecutivo (Verde/Ámbar/Rojo) sobre la factibilidad técnica y legal.

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

## 🚀 Instalación y Uso

### Requisitos previos
* Docker instalado
* Python 3.10 o superior
* Claves de API de OpenAI/Anthropic y Supabase

### Pasos para ejecución local
1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/TU_USUARIO/pj-geo-yield-ai.git](https://github.com/TU_USUARIO/pj-geo-yield-ai.git)
   cd pj-geo-yield-ai

2. **Configurar el entorno:**
Crea un archivo .env basado en .env.example con tus credenciales de API.

3. Instalar dependencias:
    ```bash
    pip install -r requirements.txt

4. Ejecutar la aplicación:
    ```bash
    XXXX

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
