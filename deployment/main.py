import uvicorn
import os
from pathlib import Path
from dotenv import load_dotenv
import logging  


#env_path = os.path.join(os.path.dirname(__file__), 'env', '.env')
#load_dotenv(env_path)

# carga las variables de entorno dese el archivo .env
# las variables de entorno se cargan a nivel de proceso, por lo que estaran disponibles en todos los módulos
load_dotenv()

# directorios del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# configuración del logging. El modulo logging controla el log a nivel de aplicación. 
# para obtener el logger en cada módulo se debe llamar a logging.getLogger("geoyield_api"), lo que permite tener un control centralizado del logging y configurar diferentes niveles de logging para diferentes módulos si se desea, aunque en este caso se ha optado por un nivel de logging global configurado a través de la variable de entorno LOG_LEVEL
log_level = int(os.getenv('LOG_LEVEL', '20'))  # Default to INFO level (20)
logging.basicConfig(level=log_level, 
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                    handlers=[
                        logging.FileHandler(str(LOG_DIR / "geoyield_api.log")),  # Log to file
                        logging.StreamHandler()  # Also log to console
                    ])
logger = logging.getLogger("geoyield_api")    

if __name__ == "__main__":
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000
                ,log_level=log_level
                ,reload=True
                )
