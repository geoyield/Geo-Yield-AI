import os
import re


def resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está definida en el entorno")

    override = os.getenv("DB_HOST_OVERRIDE")
    if override:
        url = re.sub(r"@[^:/]+:", f"@{override}:", url)

    # The host override alone is not enough when the container publishes
    # Postgres on a non-default host port (POSTGRES_HOST_PORT): the URL would
    # still point at 5432 and the connection would fail.
    port_override = os.getenv("DB_PORT_OVERRIDE")
    if port_override:
        url = re.sub(r"(@[^:/]+):\d+", rf"\g<1>:{port_override}", url)

    return url
