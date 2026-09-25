"""
Punto de entrada principal (Entrypoint) de la API.

Este script actúa como el lanzador de la aplicación. Su responsabilidad 
exclusiva, antes de arrancar el servidor web (Uvicorn), es preparar el 
entorno de ejecución:
1. Carga las variables de entorno.
2. Crea la estructura de carpetas necesaria.
3. Configura de forma centralizada el sistema de bitácoras (logging) para 
   que toda la aplicación registre sus eventos con un formato unificado.
"""

import logging
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# 1. Carga de Variables de Entorno
# Se ejecuta al principio del archivo para garantizar que los secretos y 
# configuraciones del archivo .env estén disponibles en el sistema operativo 
# ANTES de que se importen el resto de módulos de la aplicación.
load_dotenv()

# 2. Preparación del sistema de archivos para los registros (Logs)
# Calculamos la ruta absoluta de nuestro proyecto y nos aseguramos de que 
# exista la carpeta "logs". Si no existe (por ejemplo, al clonar el repo 
# de cero), la creamos automáticamente para evitar que el programa falle.
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 3. Configuración Centralizada de Bitácoras
# Leemos el nivel de detalle deseado desde el entorno (por defecto 20 = INFO).
# Definimos dos salidas (handlers):
# - FileHandler: Guarda un registro histórico persistente en un archivo físico.
# - StreamHandler: Muestra los registros en vivo por la consola de la terminal.
log_level = int(os.getenv("LOG_LEVEL", "20"))  
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_DIR / "geoyield_api.log")),
        logging.StreamHandler(),
    ],
)

# Instanciamos el logger principal que el resto de archivos utilizarán.
logger = logging.getLogger("geoyield_api")

# 4. Arranque del Servidor Uvicorn
if __name__ == "__main__":
    # Verificamos el entorno para decidir si activamos la recarga en caliente (Hot Reload).
    # En desarrollo local es muy útil que la API se reinicie sola al guardar cambios,
    # pero en producción (Docker/Nube) debe estar desactivado para no consumir 
    # recursos innecesarios ni afectar al rendimiento.
    is_dev = os.getenv("ENV", "development") == "development"

   # Lanzamos el servidor pasándole la ruta de la aplicación como texto (string), 
    # que es un requisito de Uvicorn para que el modo reload funcione correctamente.   
    uvicorn.run(
        "backend.api.api:app",
        host="0.0.0.0",
        port=8000,
        log_level=log_level,
        reload=is_dev,
    )
