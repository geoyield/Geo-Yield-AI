import os

import uvicorn
from dotenv import load_dotenv

# Carga las variables de entorno desde el .env de la raíz del repo.
# Se cargan a nivel de proceso, por lo que están disponibles en todos los
# módulos que se importen después de este punto (incluido api.py).
load_dotenv()

# Logging config now lives in backend/observability and is also invoked from
# api.py, so a `uvicorn backend.api.api:app` start (which never imports this
# module) still gets JSON output and honours LOG_LEVEL.
from backend.observability import configure_logging  # noqa: E402

configure_logging()

if __name__ == "__main__":
    # El autoreload solo tiene sentido en desarrollo local; en producción
    # (Docker/Render) debe estar desactivado. Se controla con ENV en vez de
    # dejarlo fijo en True, que era el bug original.
    is_dev = os.getenv("ENV", "development") == "development"

    uvicorn.run(
        "backend.api.api:app",
        host="0.0.0.0",
        port=8000,
        # Stops uvicorn installing its own plain-text logging config over ours.
        log_config=None,
        reload=is_dev,
    )
