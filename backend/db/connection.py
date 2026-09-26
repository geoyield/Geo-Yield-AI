"""
Database Connection Management Module.

Centralizes the logic for resolving the PostgreSQL connection URL.
Implements a "Dynamic Host Override" pattern to solve the DNS routing
problem between Docker containers and the host operating system
(Localhost).
"""

import os
import re


def resolve_database_url() -> str:
    """
    Retrieves and formats the database connection URL.

    Reads the DATABASE_URL environment variable. If the DB_HOST_OVERRIDE
    environment variable is set, uses regular expressions to replace the
    original host (usually 'postgis' from the Docker network) with the
    provided value (usually 'localhost'). If DB_PORT_OVERRIDE is also set,
    the port is replaced the same way -- needed when the container
    publishes Postgres on a non-default host port.

    Returns:
        str: The fully formatted SQLAlchemy connection string.

    Raises:
        RuntimeError: If the DATABASE_URL variable does not exist in the
            environment.
    """
    # 1. Retrieve the original URL (from .env)
    url = os.getenv("DATABASE_URL")

    # 2. Fail-fast pattern: if there's no URL, abort immediately instead of
    # letting SQLAlchemy fail later with a cryptic error.
    if not url:
        raise RuntimeError("DATABASE_URL is not defined in the environment (.env)")

    # 3. Check whether we're asked to override the host
    override = os.getenv("DB_HOST_OVERRIDE")

    # 4. Inject the new host via Regex
    if override:
        # The regex looks for "@" + (any text without ":" or "/") + ":"
        # Example: captures '@postgis:' and replaces it with '@localhost:'
        url = re.sub(r"@[^:/]+:", f"@{override}:", url)

    # The host override alone is not enough when the container publishes
    # Postgres on a non-default host port (POSTGRES_HOST_PORT): the URL would
    # still point at 5432 and the connection would fail.
    port_override = os.getenv("DB_PORT_OVERRIDE")
    if port_override:
        url = re.sub(r"(@[^:/]+):\d+", rf"\g<1>:{port_override}", url)

    return url