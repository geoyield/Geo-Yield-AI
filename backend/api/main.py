"""
Main API entrypoint.

This script acts as the application launcher. Its sole responsibility,
before starting the web server (Uvicorn), is to prepare the runtime
environment:
1. Load environment variables.
2. Configure the logging system (delegated to backend.observability, which
   is also invoked from api.py, so a direct `uvicorn backend.api.api:app`
   start is covered too).
"""

import os

import uvicorn
from dotenv import load_dotenv

# 1. Environment variable loading.
# Runs at the top of the file to guarantee that secrets and configuration
# from the .env file are available in the OS environment BEFORE the rest
# of the application's modules are imported.
load_dotenv()

# Logging config now lives in backend/observability and is also invoked from
# api.py, so a `uvicorn backend.api.api:app` start (which never imports this
# module) still gets JSON output and honours LOG_LEVEL.
from backend.observability import configure_logging  # noqa: E402

configure_logging()

# 2. Uvicorn server startup.
if __name__ == "__main__":
    # Check the environment to decide whether to enable hot reload.
    # In local development it's very useful for the API to restart itself
    # on save, but in production (Docker/cloud) it must be disabled so it
    # doesn't waste resources or affect performance.
    is_dev = os.getenv("ENV", "development") == "development"

    # We pass the app path as a string, which is a requirement for Uvicorn
    # so reload mode works correctly.
    uvicorn.run(
        "backend.api.api:app",
        host="0.0.0.0",
        port=8000,
        # Stops uvicorn installing its own plain-text logging config over ours.
        log_config=None,
        reload=is_dev,
    )