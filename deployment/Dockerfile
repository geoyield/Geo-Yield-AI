FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Se copian primero solo las dependencias para aprovechar la cache de capas
# de Docker: si el código cambia pero requirements.txt no, no se reinstalan
# paquetes en cada build.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/

EXPOSE 8000

CMD ["python", "-m", "backend.api.main"]
