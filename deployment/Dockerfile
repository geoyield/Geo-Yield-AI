#FROM python:3.10.20-slim
# Inicialmente no se había instaldo el package mariadb, por lo que cuando el container no levantaba porqué sqlalchemhy
# intentaba importarlo y no lo encontraba. Al hcerlo, enteonces fallaba la creación de la imágen porqué decía que faltaba
# el 'MariaDB Connector/C'. Se ha buscado y se ha visto que ese conector debe estar presente en el sisntema operativo
# Es por ello que se ha tenido que importar una imágen más completa de python - la estándar de dockerhub en lugar de la slim inicial
# porqué enm esa faltaba el 'mariadb C connector'
FROM python:3.11.15-trixie

ARG WORKDIR=/app

WORKDIR ${WORKDIR}

COPY ./ ./

RUN pip install -r ./requirements.txt

CMD ["python", "-m", "main"]


