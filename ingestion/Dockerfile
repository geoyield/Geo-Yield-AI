FROM python:3.11.15-trixie

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY common.py ingest_census.py ./

CMD ["python", "ingest_census.py"]
