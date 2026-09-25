"""
Módulo de Gestión de Conexión a Base de Datos.

Centraliza la lógica para resolver la URL de conexión a PostgreSQL.
Implementa un patrón de "Sobrescritura Dinámica de Host" (Host Override) 
para resolver el problema de enrutamiento DNS entre los contenedores de 
Docker y el sistema operativo anfitrión (Localhost).
"""
import os
import re

def resolve_database_url() -> str:
    """
    Recupera y formatea la URL de conexión a la base de datos.
    
    Lee la variable DATABASE_URL del entorno. Si se detecta la variable 
    de entorno DB_HOST_OVERRIDE, utiliza expresiones regulares para 
    sustituir el host original (usualmente 'postgis' de la red de Docker) 
    por el valor proporcionado (usualmente 'localhost').

    Returns:
        str: La cadena de conexión SQLAlchemy perfectamente formateada.
        
    Raises:
        RuntimeError: Si la variable DATABASE_URL no existe en el entorno.
    """
    # 1. Recuperamos la URL original (del .env)
    url = os.getenv("DATABASE_URL")

    # 2. Patrón Fail-Fast: Si no hay URL, abortamos inmediatamente en lugar de 
    # dejar que SQLAlchemy falle más adelante con un error críptico.
    if not url:
        raise RuntimeError("DATABASE_URL no está definida en el entorno (.env)")

    # 3. Comprobamos si nos piden sobrescribir el host
    override = os.getenv("DB_HOST_OVERRIDE")

    # 4. Inyección del nuevo host mediante Regex
    if override:
        # La expresión regular busca "@" + (cualquier texto sin ":" ni "/") + ":"
        # Ejemplo: Captura '@postgis:' y lo cambia por '@localhost:'
        url = re.sub(r"@[^:/]+:", f"@{override}:", url)
        
    return url