# ==============================================================================
# DOCKERFILE DE LA API (Backend)
# ==============================================================================
# Este archivo define cómo se construye la imagen de nuestra aplicación FastAPI.
# Elegimos la versión "slim" (reducida) de Python 3.12 porque elimina librerías 
# del sistema operativo que no necesitamos, haciendo que el contenedor sea 
# más ligero, rápido de descargar y con menor superficie de ataques de seguridad.
FROM python:3.12-slim

# Ajustes obligatorios para ejecutar Python dentro de contenedores:
# 1. PYTHONUNBUFFERED=1: Fuerza a que los logs (prints y system logs) salgan 
#    por pantalla de inmediato sin quedarse atascados en la memoria intermedia.
# 2. PYTHONDONTWRITEBYTECODE=1: Evita que Python genere archivos basura (.pyc) 
#    en el disco duro, manteniendo la imagen limpia.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Definimos el directorio de trabajo interno del contenedor
WORKDIR /app

# ------------------------------------------------------------------------------
# ESTRATEGIA DE CACHÉ DE CAPAS (Layer Caching)
# ------------------------------------------------------------------------------
# En lugar de copiar toda la carpeta "backend" de golpe, primero copiamos 
# SOLO el archivo de dependencias (requirements.txt). 
# ¿Por qué? Si hacemos un cambio en el código fuente (ej. en api.py) pero no 
# añadimos librerías nuevas, Docker usará la memoria caché en este paso y NO 
# volverá a descargar todos los paquetes de internet. Esto reduce el tiempo 
# de compilación de varios minutos a apenas un par de segundos.
COPY backend/requirements.txt ./backend/requirements.txt

# Instalamos las librerías. Usamos --no-cache-dir para borrar el instalador 
# de pip y no desperdiciar megabytes en el contenedor final.
RUN pip install --no-cache-dir -r backend/requirements.txt

# Una vez instaladas las dependencias, ahora sí copiamos el resto de nuestro código.
COPY backend/ ./backend/

# Documentamos que internamente nuestra API trabaja por el puerto 8000.
# (Esto no lo publica al exterior por sí solo, es solo informativo. La publicación 
# real se hace en el docker-compose.yml mapeando 8080:8000).
EXPOSE 8000

# Lanzamos el servidor usando nuestro entrypoint principal (main.py).
CMD ["python", "-m", "backend.api.main"]
