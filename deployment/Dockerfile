#FROM python:3.10.20-slim
# Inicialmente no se había instaldo el package mariadb, por lo que cuando el container no levantaba porqué sqlalchemhy
# intentaba importarlo y no lo encontraba. Al hcerlo, enteonces fallaba la creación de la imágen porqué decía que faltaba
# el 'MariaDB Connector/C'. Se ha buscado y se ha visto que ese conector debe estar presente en el sisntema operativo
# Es por ello que se ha tenido que importar una imágen más completa de python - la estándar de dockerhub en lugar de la slim inicial
# porqué enm esa faltaba el 'mariadb C connector'
FROM python:3.11.15-trixie

ARG WORKDIR=/app

WORKDIR ${WORKDIR}

# el contexto de build es la raiz del repo (ver docker-compose.yml), por lo que copiamos backend/
# de forma que su paquete "api" quede en /app/api (import string "api.api:app" en main.py)
COPY backend/ ./

RUN pip install -r ./requirements.txt

CMD ["python", "-m", "api.main"]


